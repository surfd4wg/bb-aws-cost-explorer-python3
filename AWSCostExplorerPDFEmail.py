#!/usr/bin/env python3
import boto3
import pandas as pd
import numpy as np
from datetime import datetime
from botocore.exceptions import NoCredentialsError
from weasyprint import HTML, CSS
from io import BytesIO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage  # Import MIMEImage
import matplotlib.pyplot as plt
import re
import os

# AWS Boto3 Setup
session = boto3.Session()
ce = session.client('ce')
s3 = session.client('s3')

# Run Cost Explorer Report and Get Results
response = ce.get_cost_and_usage(
    TimePeriod={
        'Start': '2023-08-01',
        'End': '2023-08-14'
    },
    Granularity='DAILY',
    Metrics=['BlendedCost'],
    GroupBy=[
        {
            'Type': 'DIMENSION',
            'Key': 'SERVICE'
        }
    ]
)

# Convert Result to DataFrame
data = response['ResultsByTime'][0]['Groups']
df = pd.DataFrame(data)
df.columns = ['Service', 'Cost']

# Save DataFrame to CSV and Upload to S3
csv_filename = f'cost_report_{datetime.now().strftime("%Y-%m-%d")}.csv'
df.to_csv(csv_filename, index=False)

s3_bucket_name = '<your bucket name>'
s3_object_name = f'<your bucket name>/cost-report/{csv_filename}'
s3.upload_file(csv_filename, s3_bucket_name, s3_object_name)

# Clean 'Cost' column data by removing non-numeric characters
df['Cost'] = df['Cost'].astype(str).apply(lambda x: re.sub(r'[^0-9.]', '', x))

# Convert 'Cost' column to numeric
try:
    df['Cost'] = pd.to_numeric(df['Cost'])
except ValueError as e:
    print("Error converting 'Cost' column to numeric:", e)
    exit(1)

# Extract 'Service' and 'Cost' data
data = response['ResultsByTime'][0]['Groups']
service_list = [entry['Keys'][0] for entry in data]
cost_list = [float(entry['Metrics']['BlendedCost']['Amount']) for entry in data]

# Create DataFrame
df = pd.DataFrame({'Service': service_list, 'Cost': cost_list})

# Create a Bar Chart from the DataFrame
plt.figure(figsize=(10, 10))
plt.bar(df['Service'], df['Cost'])
plt.xlabel('Service')
plt.ylabel('Cost')
plt.title('Cost by Service')
plt.xticks(rotation=45, ha='right')
plt.tight_layout()

# Adjust y-axis ticks and labels
plt.yticks(range(0, int(df['Cost'].max()) + 1, 1000))  # Adjust the step (100) as needed

# Adjust y-axis limits to set more height
plt.ylim(0, int(df['Cost'].max()) + 1000)  # Adjust the upper limit (100) as needed

plt.tight_layout()

# Save the chart as an image
chart_image_filename = f'chart_{datetime.now().strftime("%Y-%m-%d")}.png'
plt.savefig(chart_image_filename)

# Convert the chart image to HTML
chart_html = f'<img src="cid:{chart_image_filename}" alt="Cost Chart" width="800" height="600">'

# Upload the chart image to S3
s3_bucket_name = '<your bucket name>'
s3_object_name = f'<your bucket name>/cost-images/{chart_image_filename}'
s3.upload_file(chart_image_filename, s3_bucket_name, s3_object_name)

# Convert CSV to HTML
html = df.to_html()

# Convert HTML to PDF
pdf_file = BytesIO()
HTML(string=html).write_pdf(pdf_file)

# Send Email with PDF Attachment
smtp_server = 'email-smtp.us-east-1.amazonaws.com'
smtp_port = 587
smtp_username = '<your access key>'
smtp_password = '<your secret access key>'
from_email = 'your from email address' 

recipient_email = 'the to email address'

sender_email = '<sender email key>'
sender_password = '<the sender password key>'
receiver_email = '<to email...again>'

#email_from = 'your-email@example.com'
#email_to = 'recipient@example.com'
subject = 'Cost Report'
body = 'Attached is the cost report PDF.'

msg = MIMEMultipart()
msg['From'] = from_email
msg['To'] = receiver_email
msg['Subject'] = subject

msg.attach(MIMEText(body, 'plain'))

# Attach the PDF report
pdf_attachment = MIMEApplication(pdf_file.getvalue(), Name='cost_report.pdf')
pdf_attachment['Content-Disposition'] = f'attachment; filename=cost_report.pdf'
msg.attach(pdf_attachment)

# Attach the chart
chart_image_data = open(chart_image_filename, 'rb').read()
chart_image_attachment = MIMEImage(chart_image_data, name=os.path.basename(chart_image_filename))
chart_image_attachment.add_header('Content-ID', f'<{chart_image_filename}>')
msg.attach(chart_image_attachment)

try:
    server = smtplib.SMTP(smtp_server, smtp_port)  # Update with your SMTP server details
    server.starttls()
    server.login(sender_email, sender_password)
    server.sendmail(from_email, receiver_email, msg.as_string())
    server.quit()
    print('Email sent successfully.')
except NoCredentialsError:
    print('Failed to send email. Credentials not found.')
