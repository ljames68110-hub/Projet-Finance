import smtplib, os
host = os.getenv("SMTP_HOST","127.0.0.1")
port = int(os.getenv("SMTP_PORT","1026"))
print("TEST smtplib ->", host, port)
try:
    s = smtplib.SMTP(host, port, timeout=5)
    s.set_debuglevel(1)
    s.noop()
    s.quit()
    print("SMTPLIB OK")
except Exception as e:
    print("SMTPLIB ERR", repr(e))
