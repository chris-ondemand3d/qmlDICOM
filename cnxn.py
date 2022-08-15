# imports for SQL data part
import pyodbc
from datetime import datetime, timedelta
import pandas as pd

# imports for sending email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

cnxn_str = ("Driver={SQL Server Native Client 11.0};"
            "Server=localhost;"
            "Database=OD3DSDB_In2Guide;"
            "UID=SA;"
            "PwD=Testing1122;"
)

cnxn = pyodbc.connect(cnxn_str)

#cursor = cnxn.cursor()
#cursor.execute("SELECT COUNT(*) FROM STUDY")
#data = pd.read_sql("SELECT YEAR(StudyDateTime),COUNT(*) FROM STUDY GROUP BY YEAR(StudyDateTime) ORDER BY YEAR(StudyDateTime)",cnxn)
#print(data)
cur = cnxn.cursor()
sopinstance_uid = '1.2.392.200036.9116.2.2.2.1762667901.1166063907.765631'
cur.execute("SELECT pathname, filename FROM image WHERE SOPInstanceUID = '%s'" % sopinstance_uid)
for row in cur:
    print(row[0]+'\\'+row[1])