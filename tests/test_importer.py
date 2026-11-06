from pathlib import Path

from mass_properties.importer import read_csv, validate_row

HEADER = "id,name,parent_id,mass,cg_x,cg_y,cg_z,ixx,iyy,izz,ixy,ixz,iyz\n"


def write(tmp_path: Path, rows: str) -> Path:
    path = tmp_path / "data.csv"
    path.write_text(HEADER + rows, encoding="utf-8")
    return path


def test_valid_file_imports(tmp_path):
    result = read_csv(write(tmp_path, "ac,Aircraft,,0,0,0,0,,,,,,\nfus,Fuselage,ac,500,5,0,0,10,200,200,0,0,0\n"))
    assert result.ok
    assert [c.id for c in result.components] == ["ac", "fus"]


def test_negative_mass_rejected():
    comp, problems = validate_row({"id": "x", "name": "X", "mass": "-1", "cg_x": "0", "cg_y": "0", "cg_z": "0"})
    assert comp is None
    assert any("negative" in p for p in problems)


def test_missing_coordinate_rejected():
    comp, problems = validate_row({"id": "x", "name": "X", "mass": "1", "cg_x": "0", "cg_y": "", "cg_z": "0"})
    assert comp is None
    assert any("cg_y" in p for p in problems)


def test_non_numeric_rejected():
    _, problems = validate_row({"id": "x", "name": "X", "mass": "heavy", "cg_x": "0", "cg_y": "0", "cg_z": "0"})
    assert any("not a number" in p for p in problems)


def test_triangle_inequality_rejected():
    row = {"id": "x", "name": "X", "mass": "1", "cg_x": "0", "cg_y": "0", "cg_z": "0",
           "ixx": "1", "iyy": "1", "izz": "5"}
    _, problems = validate_row(row)
    assert any("izz exceeds" in p for p in problems)


def test_unknown_parent_rejected(tmp_path):
    result = read_csv(write(tmp_path, "fus,Fuselage,ghost,500,5,0,0,,,,,,\n"))
    assert not result.ok
    assert "unknown parent_id" in str(result.errors[0])


def test_cross_row_error_reports_csv_row_number(tmp_path):
    # The orphan is the 3rd data row; the invalid first row must not shift its number.
    result = read_csv(write(tmp_path, "bad,Bad,,-1,0,0,0,,,,,,\nac,A,,0,0,0,0,,,,,,\norphan,O,ghost,1,0,0,0,,,,,,\n"))
    orphan_errors = [e for e in result.errors if e.component_id == "orphan"]
    assert orphan_errors[0].row == 3


def test_known_parent_from_database_accepted(tmp_path):
    result = read_csv(write(tmp_path, "fus,Fuselage,ac,500,5,0,0,,,,,,\n"), known_ids=["ac"])
    assert result.ok


def test_cycle_rejected(tmp_path):
    result = read_csv(write(tmp_path, "a,A,b,1,0,0,0,,,,,,\nb,B,a,1,0,0,0,,,,,,\n"))
    assert any("cycle" in str(e) for e in result.errors)


def test_duplicate_id_rejected(tmp_path):
    result = read_csv(write(tmp_path, "a,A,,1,0,0,0,,,,,,\na,A2,,1,0,0,0,,,,,,\n"))
    assert any("duplicate id" in str(e) for e in result.errors)


def test_missing_columns_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("id,name,mass\na,A,1\n", encoding="utf-8")
    result = read_csv(path)
    assert "missing columns" in str(result.errors[0])
