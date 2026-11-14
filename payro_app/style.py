"""Look of the PayRo demo app: one phone on an otherwise empty page."""
from __future__ import annotations

CSS = """
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#e7ebf0;
font:16px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#17202b}
.phone{width:380px;min-height:740px;margin:20px;background:#f6f8fa;border:10px solid #17202b;border-radius:42px;
overflow:hidden;display:flex;flex-direction:column;box-shadow:0 18px 50px rgba(23,32,43,.25)}
.bar{background:#0b6e4f;color:#fff;padding:18px 20px 14px;display:flex;justify-content:space-between;align-items:center}
.bar b{font-size:21px;letter-spacing:.2px} .bar span{font-size:13px;opacity:.9}
.bal{background:#0b6e4f;color:#fff;padding:0 20px 22px} .bal small{display:block;opacity:.85;font-size:13px}
.bal strong{font-size:30px}
.body{padding:16px 16px 20px;flex:1} h2{font-size:17px;margin:4px 0 10px}
label{display:block;font-size:12px;color:#5b6876;margin:10px 0 3px}
input[type=text]{width:100%;font:inherit;padding:10px 12px;border:1px solid #cfd6de;border-radius:10px;background:#fff}
.opts{display:flex;gap:10px;margin-top:14px} .opt{flex:1;margin:0;position:relative}
.opt input{position:absolute;opacity:0}
.opt span{display:block;border:2px solid #cfd6de;border-radius:12px;padding:9px 11px;background:#fff;font-size:15px;
color:#17202b;cursor:pointer} .opt small{display:block;color:#5b6876;font-size:12px}
.opt b{display:block;font-size:17px;margin-top:5px} .opt input:checked+span{border-color:#0b6e4f;background:#eef8f3}
button,.btn{display:block;width:100%;margin-top:16px;padding:13px;border:0;border-radius:12px;background:#0b6e4f;
color:#fff;font:inherit;font-weight:600;text-align:center;text-decoration:none;cursor:pointer}
.btn.alt{background:#fff;color:#17202b;border:1px solid #cfd6de;margin-top:10px}
.err{background:#fde8e8;color:#8f1d1d;border-radius:10px;padding:9px 12px;margin-bottom:6px;font-size:14px}
.list{margin-top:20px} .item{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:10px 0;
border-top:1px solid #e3e8ed;font-size:15px} .item small{display:block;color:#5b6876;font-size:12px}
.item b{white-space:nowrap} .in{color:#0b6e4f} .wait{color:#8a6d1a}
.done{text-align:center;padding-top:30px} .tick{width:74px;height:74px;border-radius:50%;background:#0b6e4f;color:#fff;
font-size:40px;line-height:74px;margin:0 auto 12px} .warn .tick{background:#c98a00}
.done h1{font-size:23px;margin:0} .done p{margin:6px 0 18px;color:#5b6876}
.done small{display:block;color:#8a94a0;font-size:11px;word-break:break-word}
.rows{background:#fff;border-radius:12px;padding:2px 14px;text-align:left;font-size:15px}
.rows div{display:flex;justify-content:space-between;gap:10px;padding:10px 0;border-top:1px solid #eef1f4}
.rows div:first-child{border-top:0} .rows span:first-child{white-space:nowrap;color:#5b6876}
.rows span:last-child{text-align:right}
.new{background:#eef8f3;border:1px solid #bfe3d2;border-radius:12px;padding:12px 14px;margin-bottom:14px;font-size:14px}
.new b{display:block;font-size:24px;color:#0b6e4f}
"""


def page(body: str, refresh: int = 0) -> str:
    """A whole page that holds one phone. `refresh`: reload every N seconds (the receiver's phone)."""
    meta = f"<meta http-equiv='refresh' content='{refresh}'>" if refresh else ""
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>{meta}"
            "<meta name='viewport' content='width=device-width, initial-scale=1'><title>PayRo</title>"
            f"<style>{CSS}</style></head><body>{body}</body></html>")


def eur(value: float) -> str:
    return f"{value:,.2f} EUR"


def iban_text(iban: str) -> str:
    return " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))
