#!/usr/bin/python3
"""https://stackoverflow.com/questions/3362600/how-to-send-email-attachments"""

import argparse
import json
import smtplib
from os.path import basename
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate

credentials_file = 'avs_cred.json'
with open(credentials_file) as fp:
    credentials = json.load(fp)
mail_user = credentials['mail_user']
mail_pass = credentials['mail_pass']
mail_server = credentials['mail_server']


def send_mail(subject, body, send_from=mail_user, send_to=[mail_user], files=None):
    assert isinstance(send_to, list)

    msg = MIMEMultipart()
    msg['From'] = send_from
    msg['To'] = COMMASPACE.join(send_to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject

    msg.attach(MIMEText(body))

    for f in files or []:
        with open(f, "rb") as fil:
            part = MIMEApplication(
                fil.read(),
                Name=basename(f)
            )
        # After the file is closed
        part['Content-Disposition'] = 'attachment; filename="%s"' % basename(f)
        msg.attach(part)

    smtp = smtplib.SMTP(mail_server)
    smtp.starttls()
    smtp.login(mail_user, mail_pass)
    smtp.sendmail(send_from, send_to, msg.as_string())
    smtp.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--send_to', nargs='+', default=[mail_user])
    parser.add_argument('--subject', default='[No subject]')
    parser.add_argument('--body', default='[No body]')
    parser.add_argument('--files', nargs='+', default=None)
    args = parser.parse_args()
    # print(args)
    print('Sending mail...')
    print(f'   From: {mail_user}')
    print(f'   To: {args.send_to}')
    print(f'   Subject: {args.subject}')
    print(f'   Body: {args.body}')
    print(f'   Attachments: {args.files}')
    send_mail(subject=args.subject, body=args.body, send_to=args.send_to, files=args.files)
    print('Done.')
