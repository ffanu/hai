#!/usr/bin/env python3
"""Attachment parser QA for hai.harmonika.id.

Creates tiny TXT/CSV/DOCX/XLSX files in memory and posts them to
`/api/attachments/parse`. No third-party Python dependency is required.

Example:
  python3 scripts/hai_attachment_qa.py --base-url https://hai.harmonika.id
"""

from __future__ import annotations

import argparse
import io
import json
import time
import urllib.error
import urllib.request
import uuid
import zipfile


def docx_bytes(text: str) -> bytes:
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>
</w:document>"""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""")
        archive.writestr("word/document.xml", document_xml)
    return out.getvalue()


def xlsx_bytes(text: str) -> bytes:
    sheet_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1" t="inlineStr"><is><t>{text}</t></is></c></row>
  </sheetData>
</worksheet>"""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""")
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return out.getvalue()


def multipart_body(field_name: str, filename: str, content_type: str, data: bytes) -> tuple[str, bytes]:
    boundary = f"----haiAttachmentQA{uuid.uuid4().hex}"
    body = io.BytesIO()
    body.write(f"--{boundary}\r\n".encode())
    body.write(
        (
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode()
    )
    body.write(data)
    body.write(f"\r\n--{boundary}--\r\n".encode())
    return boundary, body.getvalue()


def post_file(base_url: str, filename: str, content_type: str, data: bytes) -> dict:
    boundary, body = multipart_body("file", filename, content_type, data)
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/attachments/parse",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "HAI-Attachment-QA/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8", "replace")
            return {"status": response.status, "payload": json.loads(payload)}
    except urllib.error.HTTPError as error:
        payload = error.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(payload)
        except Exception:
            parsed = {"raw": payload}
        return {"status": error.code, "payload": parsed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://hai.harmonika.id")
    args = parser.parse_args()

    marker = f"HAI-ATTACH-QA-{int(time.time() * 1000)}"
    cases = [
        ("txt", "qa.txt", "text/plain", f"{marker}-TXT".encode()),
        ("csv", "qa.csv", "text/csv", f"name,code\nqa,{marker}-CSV\n".encode()),
        (
            "docx",
            "qa.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            docx_bytes(f"{marker}-DOCX"),
        ),
        (
            "xlsx",
            "qa.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            xlsx_bytes(f"{marker}-XLSX"),
        ),
    ]
    results = []
    ok = True
    for label, filename, mime, data in cases:
        result = post_file(args.base_url, filename, mime, data)
        text = str(result.get("payload", {}).get("file", {}).get("text", ""))
        expected = f"{marker}-{label.upper()}"
        passed = result.get("status") == 200 and result.get("payload", {}).get("ok") is True and expected in text
        ok = ok and passed
        results.append({
            "type": label,
            "status": result.get("status"),
            "ok": passed,
            "expected": expected,
            "text_sample": text[:160],
            "error": result.get("payload", {}).get("error") or result.get("payload", {}).get("message"),
        })

    print(json.dumps({
        "ok": ok,
        "base_url": args.base_url,
        "marker": marker,
        "results": results,
    }, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
