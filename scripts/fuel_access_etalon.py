# -*- coding: utf-8 -*-
"""
Эталон расчёта топлива из Access СиПР.

Копирует «СиПР ЭЭС_2031_4 этап.mdb», на форме «Расчет» для каждой ОЭС
и года 2026–2031 жмёт Коэфф → Распред → Топливо (без формы ограничений),
пишет результаты в эталонный MDB и выгружает TSV для сверки с АРМ.

  python scripts/fuel_access_etalon.py copy
  python scripts/fuel_access_etalon.py list
  python scripts/fuel_access_etalon.py run [--oes 1] [--year 2026] [--fresh]
  python scripts/fuel_access_etalon.py export
  python scripts/fuel_access_etalon.py all

Если Access COM недоступен: copy, откройте эталонный MDB, пройдите list
вручную (Коэфф / Распред / Топливо на каждой строке), затем export.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
ETALON_DIR = ROOT / "_otet_analysis" / "sipr_etalon"
COM_LOG = ETALON_DIR / "access_run.log"
SIPR_CHECK = ROOT / "_otet_analysis" / "sipr_check"
DEFAULT_SRC = Path(
    r"c:\Users\novikova-eyu\Desktop\!!!Работа\АРМ ГС_на компе"
    r"\БД Топливо\БД Гурьева А.Ю\СиПР ЭЭС_2031_4 этап.mdb"
)
ETALON_MDB = ETALON_DIR / "sipr_ees_2031_etalon.mdb"
FORM_TXT = ETALON_DIR / "_form_Raschet.txt"
FORM_NAME_TXT = ETALON_DIR / "_form_name.txt"
MOD_BAS = ETALON_DIR / "mod_SiprEtalon.bas"
PS1 = ETALON_DIR / "_com_step.ps1"
RUN_LOG = ETALON_DIR / "run_log.txt"
YEARS = (2026, 2027, 2028, 2029, 2030, 2031)
FORM_NAME = "Расчет"
WNAME_SCHEMA = "Станции(Схема)"

STATION_EXPORT_FIELDS = [
    "NAME",
    "YEAR",
    "NUST",
    "NR",
    "E",
    "EWTP",
    "Q",
    "QOTR",
    "H",
    "HFIX",
    "OBOR",
    "VED",
    "OBL",
    "OES",
    "NUMB1120",
    "numb1",
    "v",
    "EOTP",
    "EURT",
    "EUST",
    "TURT",
    "TUST",
    "B",
    "GAZ",
    "ISK_GAZ",
    "MAZUT",
    "TORF",
    "SLAN",
    "PROCH",
    "UGOL",
    "DON",
    "PODM",
    "PECH",
    "ALT",
    "KUZN",
    "URAL",
    "BASHK",
    "KAZAH",
    "KAN",
    "TUNG",
    "IRKUT",
    "HAK",
    "TUV",
    "BUR",
    "CHIT",
    "TAL",
    "AMUR",
    "URG",
    "USHUM",
    "PRIM",
    "YAKUT",
    "MAG",
    "KAMCH",
    "CHUKOT",
    "SAH",
]


def _source_mdb() -> Path:
    env = os.environ.get("FUEL_ACCESS_ETALON_SRC", "").strip()
    if env:
        return Path(env)
    hint = SIPR_CHECK / "mdb_path.txt"
    if hint.is_file():
        raw = hint.read_text(encoding="utf-8").strip().lstrip("\ufeff")
        p = Path(raw)
        if p.is_file():
            return p
    return DEFAULT_SRC


def _ensure_dir() -> None:
    ETALON_DIR.mkdir(parents=True, exist_ok=True)


def _decode_ps(data: bytes) -> str:
    if not data:
        return ""
    for enc in ("utf-8-sig", "utf-8", "cp866", "cp1251"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _wait_access_quit(*, seconds: int = 20, kill: bool = False) -> None:
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                f"$deadline = (Get-Date).AddSeconds({int(seconds)}); "
                "while ((Get-Date) -lt $deadline) { "
                "  $p = @(Get-Process -Name MSACCESS -ErrorAction SilentlyContinue); "
                "  if ($p.Count -eq 0) { break }; "
                "  Start-Sleep -Milliseconds 400 "
                "}"
                + (
                    "; Get-Process -Name MSACCESS -ErrorAction SilentlyContinue "
                    "| Stop-Process -Force"
                    if kill
                    else ""
                )
            ),
        ],
        capture_output=True,
        timeout=seconds + 15,
    )


def _ps(script: str, *, timeout: int = 3600) -> str:
    _ensure_dir()
    header = (
        "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)\n"
        "$OutputEncoding = [Console]::OutputEncoding\n"
        "$ErrorActionPreference = 'Continue'\n"
    )
    PS1.write_text(header + script, encoding="utf-8-sig")
    r = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PS1),
        ],
        capture_output=True,
        timeout=timeout,
    )
    out = _decode_ps(r.stdout) + _decode_ps(r.stderr)
    prev = COM_LOG.read_text(encoding="utf-8", errors="replace") if COM_LOG.is_file() else ""
    stamp = f"\n===== rc={r.returncode} =====\n"
    COM_LOG.write_text(prev + stamp + out + ("\n" if not out.endswith("\n") else ""), encoding="utf-8")
    try:
        sys.stdout.write(out)
        if not out.endswith("\n"):
            sys.stdout.write("\n")
    except UnicodeEncodeError:
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        sys.stdout.buffer.write(b"\n")
    if r.returncode != 0:
        raise SystemExit(f"PowerShell failed rc={r.returncode}")
    return out


def cmd_copy(*, fresh: bool) -> Path:
    src = _source_mdb()
    if not src.is_file():
        raise SystemExit(f"Исходный MDB не найден: {src}")
    _ensure_dir()
    if ETALON_MDB.is_file() and not fresh:
        print(f"уже есть {ETALON_MDB} (для новой копии: --fresh)")
        return ETALON_MDB
    print(f"copy {src} -> {ETALON_MDB}")
    shutil.copy2(src, ETALON_MDB)
    meta = ETALON_DIR / "source.txt"
    meta.write_text(
        f"src={src}\nsize={src.stat().st_size}\nmtime={src.stat().st_mtime}\n",
        encoding="utf-8",
    )
    print(f"скопировано {ETALON_MDB.stat().st_size} байт")
    return ETALON_MDB


def _oledb_query(sql: str, out_tsv: Path) -> None:
    mdb = str(ETALON_MDB)
    out = str(out_tsv)
    _ps(
        rf'''
$ErrorActionPreference = "Stop"
$mdb = @'
{mdb}
'@
$out = @'
{out}
'@
function Open-Etalon() {{
  $providers = @(
    "Provider=Microsoft.ACE.OLEDB.16.0;Data Source=$mdb;Persist Security Info=False;",
    "Provider=Microsoft.ACE.OLEDB.12.0;Data Source=$mdb;Persist Security Info=False;",
    "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$mdb;Persist Security Info=False;"
  )
  $last = $null
  foreach ($cs in $providers) {{
    try {{
      $c = New-Object System.Data.OleDb.OleDbConnection($cs)
      $c.Open()
      return $c
    }} catch {{
      $last = $_
    }}
  }}
  throw $last
}}
$conn = Open-Etalon
try {{
  $cmd = $conn.CreateCommand()
  $cmd.CommandText = @'
{sql}
'@
  $da = New-Object System.Data.OleDb.OleDbDataAdapter($cmd)
  $dt = New-Object System.Data.DataTable
  [void]$da.Fill($dt)
  $sw = New-Object System.IO.StreamWriter($out, $false, [Text.UTF8Encoding]::new($false))
  $cols = @($dt.Columns | ForEach-Object {{ $_.ColumnName }})
  $sw.WriteLine(($cols -join "`t"))
  foreach ($row in $dt.Rows) {{
    $vals = foreach ($col in $cols) {{
      $v = $row[$col]
      if ([DBNull]::Value.Equals($v) -or $null -eq $v) {{ "" }}
      else {{ [string]$v }}
    }}
    $sw.WriteLine(($vals -join "`t"))
  }}
  $sw.Close()
  Write-Output ("rows=" + $dt.Rows.Count + " file=" + $out)
}} finally {{
  $conn.Close()
}}
'''
    )


def cmd_list() -> list[dict]:
    if not ETALON_MDB.is_file():
        cmd_copy(fresh=False)
    out = ETALON_DIR / "params.tsv"
    _oledb_query("SELECT * FROM [Параметры-распределения]", out)
    rows = []
    with out.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            year = _to_int(r.get("year") or r.get("YEAR"))
            if year not in YEARS:
                continue
            wname = (r.get("wname") or "").strip()
            if wname and wname != WNAME_SCHEMA:
                continue
            oes = _oes_from_filter(r.get("filter") or "")
            rows.append(
                {
                    "name": (r.get("name") or "").strip(),
                    "year": year,
                    "oes": oes,
                    "filter": (r.get("filter") or "").strip(),
                    "e": r.get("e"),
                    "lim": r.get("lim"),
                    "wname": wname,
                }
            )
    rows.sort(key=lambda x: ((x["oes"] or 99), x["year"], x["name"]))
    print(f"сценариев {len(rows)} (годы {YEARS[0]}–{YEARS[-1]}, {WNAME_SCHEMA})")
    for r in rows:
        print(
            f"  oes={r['oes']!s:>3} {r['year']}  {r['name'][:40]:40s}  "
            f"e={r['e']}  {r['filter']}"
        )
    checklist = ETALON_DIR / "manual_checklist.txt"
    lines = [
        "Ручной прогон эталона (если COM недоступен).",
        f"Файл: {ETALON_MDB}",
        "Откройте форму «Расчет». Форму «Анализ_по_областям» не открывать.",
        "Для каждой строки ниже: Коэфф → Распред → Топливо. MsgBox NR — Нет.",
        "",
    ]
    for r in rows:
        lines.append(f"[ ] oes={r['oes']} {r['year']} {r['name']}")
    checklist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"чеклист: {checklist}")
    return rows


def _to_int(v) -> int | None:
    if v is None or str(v).strip() == "":
        return None
    try:
        return int(float(str(v).replace(",", ".")))
    except (TypeError, ValueError):
        return None


def _oes_from_filter(text: str) -> int | None:
    m = re.search(r"oes\s*=\s*(\d+)", text or "", flags=re.IGNORECASE)
    if not m:
        return None
    return int(m.group(1))


def _strip_custom_controls(text: str) -> str:
    """Убрать MSComctlLib.ProgCtrl из SaveAsText, не трогая форму через DeleteControl."""
    if "MSComctlLib.ProgCtrl" not in text and 'OLEClass ="ProgCtrl"' not in text:
        print("strip ProgCtrl=0 (уже нет)")
        return text
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    n = 0
    while i < len(lines):
        m = re.match(r"^(\s*)Begin CustomControl\b", lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        indent = m.group(1)
        start = i
        i += 1
        block = [lines[start]]
        closed = False
        while i < len(lines):
            block.append(lines[i])
            body = lines[i].rstrip("\r\n")
            i += 1
            if body == f"{indent}End":
                closed = True
                break
        if not closed:
            raise SystemExit("незакрытый Begin CustomControl")
        blob = "".join(block)
        if "MSComctlLib.ProgCtrl" in blob or 'OLEClass ="ProgCtrl"' in blob:
            n += 1
            continue
        out.extend(block)
    print(f"strip ProgCtrl CustomControl={n}")
    if n < 2:
        raise SystemExit(f"ожидали 2 ProgCtrl (pb/prestr), получили {n}")
    return "".join(out)


def _comment_progctrl_code(text: str) -> str:
    text, n = re.subn(
        r"^([ \t]*)((?:pb|prestr)\.[^\r\n']+)",
        r"\1' \2  ' etalon: no ProgCtrl",
        text,
        flags=re.M,
    )
    print(f"comment pb/prestr={n}")
    if n < 1 and "etalon: no ProgCtrl" not in text:
        raise SystemExit("не удалось закомментировать pb./prestr.")
    return text


def patch_form(text: str) -> str:
    text = _strip_custom_controls(text)
    text = _comment_progctrl_code(text)
    n = 0
    for btn in ("5", "27", "49"):
        a, b = f"Private Sub Кнопка{btn}_Click()", f"Public Sub Кнопка{btn}_Click()"
        if a in text:
            text = text.replace(a, b)
            n += 1
        elif b in text:
            n += 1
    text, n2 = re.subn(
        r'^Set otet = DBEngine\.OpenDatabase\("[^"]+"\)',
        "' Set otet = Nothing  ' etalon: no F:\\ ОТЭТ",
        text,
        count=1,
        flags=re.M,
    )
    text, n3 = re.subn(
        r"^Set class = otet\.OpenRecordset\([^)]+\)",
        "' Set class = Nothing  ' etalon: no ОТЭТ names",
        text,
        flags=re.M,
    )
    text, n4 = re.subn(r'^class\.Index\s*=\s*"numb"', "' class.Index = numb", text, flags=re.M)
    text, n5 = re.subn(
        r'class\.Seek\s+"=",\s*w!numb1120\s*\r?\n'
        r"stname = class!Name\s*\r?\n"
        r"bmsg = MsgBox\([^\r\n]+\)",
        "bmsg = vbNo  ' etalon: MsgBox NR -> No",
        text,
        count=1,
    )
    text, n6 = re.subn(
        r"Private Sub Form_Open\(Cancel As Integer\)\s*\r?\n"
        r"varlst = DFirst\([^\r\n]+\)\s*\r?\n"
        r"End Sub",
        "Private Sub Form_Open(Cancel As Integer)\r\nEnd Sub",
        text,
        count=1,
    )
    print(
        f"patch: public_click={n} otet={n2} class_rs={n3} class_idx={n4} "
        f"msgbox={n5} form_open={n6}"
    )
    if n < 3:
        raise SystemExit("не удалось сделать Кнопка5/27/49 Public")
    if n5 < 1 and "etalon: MsgBox NR" not in text:
        raise SystemExit("не удалось отключить MsgBox NR")
    return text


def _write_module(oes: int | None, year: int | None, *, ping: bool = False) -> None:
    oes_check = "True" if oes is None else f"(oes = {int(oes)})"
    year_check = "True" if year is None else f"(yr = {int(year)})"
    log_path = str(RUN_LOG).replace("\\", "\\\\")
    src = f"""Private Sub LogX(ByVal s As String)
    Dim n As Integer
    n = FreeFile
    Open "{log_path}" For Append As #n
    Print #n, Now & vbTab & s
    Close #n
End Sub

Private Function NzS(ByVal v As Variant) As String
    If IsNull(v) Then
        NzS = ""
    Else
        NzS = CStr(v)
    End If
End Function

Private Function OesOf(ByVal fltr As Variant) As Long
    Dim s As String
    Dim p As Long
    s = NzS(fltr)
    p = InStr(1, LCase$(s), "oes=")
    If p = 0 Then
        OesOf = 0
        Exit Function
    End If
    s = Mid$(s, p + 4)
    OesOf = Val(s)
End Function

Private Function FormRaschet() As String
    FormRaschet = ChrW(&H420) & ChrW(&H430) & ChrW(&H441) & ChrW(&H447) & ChrW(&H435) & ChrW(&H442)
End Function

Private Function BtnClick(ByVal n As Long) As String
    BtnClick = ChrW(&H41A) & ChrW(&H43D) & ChrW(&H43E) & ChrW(&H43F) & ChrW(&H43A) & ChrW(&H430) & CStr(n) & "_Click"
End Function

Public Function SiprPing() As String
    SiprPing = "PONG"
End Function

Public Function SiprRunOne(ByVal f As Object, ByVal nm As String, ByVal yr As Long) As String
    On Error GoTo fail
    CallByName f, BtnClick(5), VbMethod
    LogX "COEFF" & vbTab & nm & vbTab & yr & vbTab & "ph=" & NzS(f!ph) & vbTab & "ch=" & NzS(f!ch)
    CallByName f, BtnClick(27), VbMethod
    LogX "DIST" & vbTab & nm & vbTab & yr & vbTab & "k=" & NzS(f!k) & vbTab & "ce=" & NzS(f!ce)
    CallByName f, BtnClick(49), VbMethod
    If f.Dirty Then f.Dirty = False
    SiprRunOne = "OK" & vbTab & nm & vbTab & yr & vbTab & "k=" & NzS(f!k) & vbTab & "ph=" & NzS(f!ph) & vbTab & "ce=" & NzS(f!ce)
    Exit Function
fail:
    SiprRunOne = "ERR" & vbTab & nm & vbTab & yr & vbTab & Err.Number & " " & Err.Description
End Function

Public Function SiprRunAll() As String
    Dim f As Object
    Dim rs As DAO.Recordset
    Dim fname As String
    Dim yr As Long
    Dim nm As String
    Dim oes As Long
    Dim n As Long
    Dim nOk As Long
    Dim nErr As Long
    Dim nSkip As Long
    Dim line As String
    On Error GoTo fail
    fname = FormRaschet()
    LogX "enter SiprRunAll"
    DoCmd.SetWarnings False
    Application.Echo False
    DoCmd.OpenForm fname, acNormal
    Set f = Forms(fname)
    Set rs = f.RecordsetClone
    If rs.EOF And rs.BOF Then
        SiprRunAll = "NO_RECORDS"
        LogX SiprRunAll
        GoTo cleanup
    End If
    rs.MoveFirst
    Do Until rs.EOF
        yr = CLng(Nz(rs!year, 0))
        nm = NzS(rs!name)
        oes = OesOf(rs!filter)
        If yr >= 2026 And yr <= 2031 Then
            If {year_check} And {oes_check} Then
                n = n + 1
                f.Bookmark = rs.Bookmark
                line = SiprRunOne(f, nm, yr)
                LogX line
                If Left$(line, 2) = "OK" Then
                    nOk = nOk + 1
                Else
                    nErr = nErr + 1
                End If
            Else
                nSkip = nSkip + 1
            End If
        End If
        rs.MoveNext
    Loop
    SiprRunAll = "done n=" & n & " ok=" & nOk & " err=" & nErr & " skip=" & nSkip
    LogX SiprRunAll
cleanup:
    On Error Resume Next
    DoCmd.Close acForm, fname, acSaveYes
    Application.Echo True
    DoCmd.SetWarnings True
    Exit Function
fail:
    SiprRunAll = "FATAL " & Err.Number & " " & Err.Description
    LogX SiprRunAll
    Resume cleanup
End Function
"""
    if ping:
        src = (
            "Public Function SiprPing() As String\r\n"
            "    SiprPing = \"PONG\"\r\n"
            "End Function\r\n"
        )
    MOD_BAS.write_bytes(src.encode("ascii"))


def _clear_startup() -> None:
    mdb = str(ETALON_MDB)
    _ps(
        rf'''
$ErrorActionPreference = "Stop"
$path = @'
{mdb}
'@
$dbe = New-Object -ComObject DAO.DBEngine.120
$db = $dbe.OpenDatabase($path)
foreach ($name in @("StartupForm", "StartUpForm")) {{
  try {{
    # Не "(none)": Access 2007 ищет форму с таким именем и падает при открытии.
    # Пустая строка DAO не принимает — ставим форму «Расчет».
    $db.Properties($name).Value = [string]([char]0x0420) + [char]0x0430 + [char]0x0441 + [char]0x0447 + [char]0x0435 + [char]0x0442
    Write-Output "updated $name"
  }} catch {{
    try {{
      $p = $db.CreateProperty($name, 10, ([string]([char]0x0420) + [char]0x0430 + [char]0x0441 + [char]0x0447 + [char]0x0435 + [char]0x0442))
      $db.Properties.Append($p)
      Write-Output "created $name"
    }} catch {{
      Write-Output "skip $name"
    }}
  }}
}}
$db.Close()
[Runtime.InteropServices.Marshal]::ReleaseComObject($db) | Out-Null
[Runtime.InteropServices.Marshal]::ReleaseComObject($dbe) | Out-Null
Write-Output "startup cleared"
'''
    )


def cmd_patch_saved_form() -> None:
    if not FORM_TXT.is_file():
        raise SystemExit(f"нет выгрузки формы: {FORM_TXT}")
    raw = FORM_TXT.read_bytes()
    if raw[:2] == b"\xff\xfe":
        text = raw.decode("utf-16")
        enc_out = "utf-16"
    else:
        try:
            text = raw.decode("utf-8")
            enc_out = "utf-8"
        except UnicodeDecodeError:
            text = raw.decode("cp1251")
            enc_out = "cp1251"
    print(f"form encoding={enc_out} chars={len(text)}")
    patched = patch_form(text)
    FORM_TXT.write_bytes(patched.encode(enc_out))
    print(f"patched {FORM_TXT}")


def cmd_run(*, oes: int | None, year: int | None, fresh: bool, skip_patch: bool, ping: bool = False) -> None:
    del ping  # оставлен для совместимости CLI
    _wait_access_quit(seconds=8, kill=False)
    try:
        cmd_copy(fresh=fresh)
    except PermissionError:
        _wait_access_quit(seconds=8, kill=True)
        cmd_copy(fresh=fresh)
    _ensure_dir()
    COM_LOG.write_text("", encoding="utf-8")
    if not RUN_LOG.is_file() or fresh:
        RUN_LOG.write_text("", encoding="utf-8")
    _clear_startup()
    tpl = (ETALON_DIR / "_run_buttons.ps1.tpl").read_text(encoding="utf-8")
    script = (
        tpl.replace("__DST__", str(ETALON_MDB))
        .replace("__RUNLOG__", str(RUN_LOG))
        .replace("__FORM_TXT__", str(FORM_TXT))
        .replace("__PYTHON__", sys.executable)
        .replace("__ETALON_PY__", str(Path(__file__).resolve()))
        .replace("__FILTER_OES__", "$null" if oes is None else str(int(oes)))
        .replace("__FILTER_YEAR__", "$null" if year is None else str(int(year)))
        .replace("__DO_FORM__", "$false" if skip_patch else "$true")
    )
    _ps(script, timeout=8 * 3600)
    print(f"лог COM: {COM_LOG}")
    print(f"лог VBA: {RUN_LOG}")



def _bracket_fields(names: list[str]) -> str:
    return ", ".join(f"[{n}]" for n in names)


def cmd_export() -> None:
    if not ETALON_MDB.is_file():
        raise SystemExit(f"нет эталона: {ETALON_MDB} (сначала copy/run)")
    years_sql = ",".join(str(y) for y in YEARS)
    st_sql = (
        "SELECT "
        + _bracket_fields(STATION_EXPORT_FIELDS)
        + " FROM [Станции(Схема)] WHERE [YEAR] IN ("
        + years_sql
        + ") AND [VED]>0"
    )
    _oledb_query(st_sql, ETALON_DIR / "stations.tsv")
    _oledb_query(
        "SELECT * FROM [Доп_угли(Схема)] WHERE [YEAR] IN (" + years_sql + ")",
        ETALON_DIR / "extra.tsv",
    )
    _oledb_query("SELECT * FROM [Параметры-распределения]", ETALON_DIR / "params.tsv")
    print(f"выгрузка в {ETALON_DIR}")


def cmd_all(args: argparse.Namespace) -> None:
    cmd_copy(fresh=args.fresh)
    cmd_list()
    cmd_run(oes=args.oes, year=args.year, fresh=False, skip_patch=args.skip_patch)
    cmd_export()


def main() -> int:
    parser = argparse.ArgumentParser(description="Эталон Access: Коэфф / Распред / Топливо")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_copy = sub.add_parser("copy", help="Скопировать исходный СиПР MDB")
    p_copy.add_argument("--fresh", action="store_true")

    sub.add_parser("list", help="Список ОЭС×годы и чеклист для ручного прогона")

    p_run = sub.add_parser("run", help="COM: три кнопки по всем (или выбранным) ОЭС/годам")
    p_run.add_argument("--oes", type=int, default=None)
    p_run.add_argument("--year", type=int, default=None)
    p_run.add_argument("--fresh", action="store_true", help="Перезаписать эталон из исходника")
    p_run.add_argument("--skip-patch", action="store_true", help="Не перезаписывать форму из SaveAsText")
    p_run.add_argument("--ping", action="store_true", help="Только SiprPing, без трёх кнопок")

    sub.add_parser("export", help="Выгрузить Станции / Доп_угли / параметры в TSV")
    sub.add_parser("patch-form", help="Патч SaveAsText формы (ProgCtrl, OTET, Public кнопки)")

    p_all = sub.add_parser("all", help="copy + list + run + export")
    p_all.add_argument("--oes", type=int, default=None)
    p_all.add_argument("--year", type=int, default=None)
    p_all.add_argument("--fresh", action="store_true")
    p_all.add_argument("--skip-patch", action="store_true")

    args = parser.parse_args()
    if args.cmd == "copy":
        cmd_copy(fresh=args.fresh)
    elif args.cmd == "list":
        cmd_list()
    elif args.cmd == "run":
        cmd_run(oes=args.oes, year=args.year, fresh=args.fresh, skip_patch=args.skip_patch, ping=args.ping)
    elif args.cmd == "export":
        cmd_export()
    elif args.cmd == "patch-form":
        cmd_patch_saved_form()
    elif args.cmd == "all":
        cmd_all(args)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
