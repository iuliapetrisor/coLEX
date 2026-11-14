"""Stylesheet and fixed texts of the PayRo demo page."""

CSS = """
body{font:16px/1.4 system-ui,sans-serif;margin:0;background:#eef1f6;color:#1b1f2a}
.top{background:#0b6e4f;color:#fff;padding:10px 22px} .top b{font-size:20px} .top small{opacity:.9;display:block}
main{max-width:1080px;margin:0 auto;padding:14px 20px}
.tabs a{display:inline-block;padding:7px 14px;margin:0 6px 8px 0;border-radius:18px;background:#fff;
border:1px solid #c9d0db;color:#1b1f2a;text-decoration:none} .tabs a.on{background:#0b6e4f;color:#fff}
form.in{background:#fff;border:1px solid #d5dae3;border-radius:10px;padding:10px 14px;margin-bottom:14px}
form.in label{margin-right:14px;font-size:14px} input,select,button{font:inherit;padding:3px 6px}
button{background:#0b6e4f;color:#fff;border:0;border-radius:6px;padding:5px 14px;cursor:pointer}
.pair{display:flex;gap:26px;flex-wrap:wrap;justify-content:center}
.phone{width:360px;background:#fff;border:9px solid #1b1f2a;border-radius:34px;padding:0 0 14px;overflow:hidden}
.bar{background:#0b6e4f;color:#fff;padding:12px 16px;font-weight:700;font-size:19px}
.bar span{float:right;font-size:11px;font-weight:400;border:1px solid #fff;border-radius:8px;padding:1px 6px;margin-top:4px}
.ver{font-size:13px;padding:7px 16px} .ver.live{background:#e4f3ec} .ver.draft{background:#fff3cd}
h3{margin:12px 16px 6px} .row{padding:7px 16px;border-bottom:1px solid #edf0f4}
.row span{display:block;font-size:12px;color:#667} .row small{display:block;color:#667}
.opts{display:flex;gap:8px;padding:10px 16px}
.opt{flex:1;border:2px solid #d5dae3;border-radius:10px;padding:8px;font-size:13px}
.opt.sel{border-color:#0b6e4f;background:#f1faf6} .opt b{display:block;font-size:19px}
.cmp{margin:0 16px 8px;padding:5px 9px;border-radius:7px;font-size:14px;font-weight:600}
.good{color:#17603a} .bad{color:#a31515} .cmp.good{background:#e4f3ec} .cmp.bad{background:#fde8e8}
.out{margin:8px 16px;padding:10px;border-radius:9px} .out.good{background:#e4f3ec}
.out.warn{background:#fff3cd;color:#5c4400} .out.bad{background:#fde8e8}
.btn{display:inline-block;margin-top:8px;background:#5c4400;color:#fff;padding:5px 10px;border-radius:6px;
text-decoration:none;font-size:14px} .chk{font-size:13px;padding:2px 16px;color:#445} .chk ul{margin:4px 0;padding-left:18px}
.law{background:#fff;border:1px solid #d5dae3;border-radius:10px;padding:10px 16px;margin-top:16px}
blockquote{margin:8px 0;padding:4px 12px;border-left:4px solid #0b6e4f;font-size:15px}
code{font:13px ui-monospace,monospace} .note{font-size:13px;color:#556;margin-top:12px}
"""

WHAT_IS_REAL = ("FICTIONAL – PayRo SRL is a fabricated company. Simulated on this page: the bank's account directory "
                "and the SMS code. Real: the fees and the transfer logic, executed from each version of the repository.")
