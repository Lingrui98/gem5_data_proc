#!/usr/bin/python3
# -*- coding: UTF-8 -*-

import os
import smtplib
import zipfile
import tarfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

def to_tar(file='data'):
    path = os.path.isdir(file)
    with tarfile.open(file+'.tar.gz', "w:gz") as tar:
        if path:
            tar.add(file, arcname=os.path.basename(file))
        else:
            tar.add(file, arcname=file)

#    sp = os.split(file,'.')
#    zf = zipfile.ZipFile(sp[0]+'.zip',mode='w')


#    zf = zipfile.ZipFile(file+'.zip', mode='w', zipfile.ZIP_DEFLATED)

def send_mail_from_ucas(to='goulingrui@ict.ac.cn', subject='data', attach=None):
    # 第三方 SMTP 服务
    mail_host="smtp.cstnet.cn"  #设置服务器
    mail_user="goulingrui15@mails.ucas.ac.cn"    #用户名
    mail_pass="glr_0831"   #口令

    sender = 'goulingrui15@mails.ucas.ac.cn'
    receivers = ['goulingrui@ict.ac.cn']  # 接收邮件，可设置为你的QQ邮箱或者其他邮箱

    #创建一个带附件的实例
    message = MIMEMultipart()
    message['From'] = Header("glr", 'utf-8')
    message['To'] =  Header(to, 'utf-8')
    message['Subject'] = Header(subject, 'utf-8')

    #邮件正文内容
    message.attach(MIMEText('……', 'plain', 'utf-8'))

    # 构造附件1，传送当前目录下的 test.txt 文件
    try:
        att1 = MIMEText(open(attach, 'rb').read(), 'base64', 'utf-8')
        att1["Content-Type"] = 'application/octet-stream'
        # 这里的filename可以任意写，写什么名字，邮件中显示什么名字
        att1["Content-Disposition"] = 'attachment; filename="'+attach+'"'
        message.attach(att1)
    except Exception as e:
        print(e)

    try:
        smtpObj = smtplib.SMTP()
        smtpObj.connect(mail_host, 25)
        smtpObj.login(mail_user, mail_pass)
        smtpObj.sendmail(sender, receivers, message.as_string())
        print("邮件发送成功")
    except smtplib.SMTPException as e:
        print("Error: 无法发送邮件", e)

if __name__ == '__main__':
    to_tar()
    send_mail_from_ucas(attach='data.tar.gz')
