from flask import Flask
from flask import render_template, flash, request, redirect, url_for
import os
from werkzeug.utils import secure_filename
import json
import mysql.connector
import boto3
from botocore.exceptions import ClientError

UPLOAD_FOLDER = 'media'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])



app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = "secret key"


with open('config.json') as json_file:
    data = json.load(json_file)
    app.config['RDS_ENDPOINT'] = data['rds-endpoint'] if "rds-endpoint" in data else ""
    app.config['RDS_USER'] = data['rds-user'] if "rds-user" in data else ""
    app.config['RDS_PASSWORD'] = data['rds-password'] if "rds-password" in data else ""
    app.config['S3_BUCKETNAME'] = data['s3-bucketname'] if "s3-bucketname" in data else ""
    app.config['S3_REGION'] = data['s3-region'] if "s3-region" in data else ""





@app.route('/')
def index():
    confg_data = {
        'rds_endpoint': app.config['RDS_ENDPOINT'],'rds_user': app.config['RDS_USER'],
        'rds_password': app.config['RDS_PASSWORD'],
        's3_bucketname': app.config['S3_BUCKETNAME'], 's3_region':app.config['S3_REGION']
    }
    posts=[]
    try :
        mydb = mysql.connector.connect(
          host=app.config['RDS_ENDPOINT'],
          user=app.config['RDS_USER'],
          passwd=app.config['RDS_PASSWORD'],
          database="awsdb"
        )
        cursor = mydb.cursor(dictionary=True)
        qry = "SELECT * FROM `posts`"
        cursor.execute(qry)
        posts = cursor.fetchall()
        cursor.close()
    except Exception as e:
        print(e)

    return render_template('index.html' ,data=confg_data,posts=posts)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_sql(filename):
    data = open(filename, 'r').readlines()
    stmts = []
    DELIMITER = ';'
    stmt = ''

    for lineno, line in enumerate(data):
        if not line.strip():
            continue

        if line.startswith('--'):
            continue

        if 'DELIMITER' in line:
            DELIMITER = line.split()[1]
            continue

        if (DELIMITER not in line):
            stmt += line.replace(DELIMITER, ';')
            continue

        if stmt:
            stmt += line
            stmts.append(stmt.strip())
            stmt = ''
        else:
            stmts.append(line.strip())
    return stmts
@app.route('/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':

        data = request.form.to_dict()

        app.config['RDS_ENDPOINT'] = data['rds-endpoint'] if "rds-endpoint" in data else ""
        app.config['RDS_USER'] = data['rds-user'] if "rds-user" in data else ""
        app.config['RDS_PASSWORD'] = data['rds-password'] if "rds-password" in data else ""
        app.config['S3_BUCKETNAME'] = data['s3-bucketname'] if "s3-bucketname" in data else ""
        app.config['S3_REGION'] = data['s3-region'] if "s3-region" in data else ""

        try :
            mydb = mysql.connector.connect(
              host=app.config['RDS_ENDPOINT'],
              user=app.config['RDS_USER'],
              passwd=app.config['RDS_PASSWORD']
            )
            mydb.autocommit = True
            cursor = mydb.cursor()
            stmts = parse_sql('awsdb.sql')
            for stmt in stmts:
                cursor.execute(stmt)
            cursor.close()

        except Exception as e:
            print(e)
            #return redirect("/")

        with open('config.json', 'w') as outfile:
            json.dump(data, outfile)

        with open('config.json', 'rb') as file:
            session = boto3.Session(
                    region_name=app.config['S3_REGION']
                )
            s3 = session.resource('s3')
            bucket = s3.Bucket(app.config['S3_BUCKETNAME'])
            bucket.put_object(Body=file,
                          Key="config.json",
                          ACL='authenticated-read')


    return redirect("/")


@app.route('/post', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':

        # check if the post request has the file part
        if 'file' not in request.files:
            #flash('No file part')
            return redirect("/")
        file = request.files['file']

        session = boto3.Session(
                region_name=app.config['S3_REGION']
            )
        s3 = session.resource('s3')
        bucket = s3.Bucket(app.config['S3_BUCKETNAME'])






        if file.filename == '':
            flash('No selected file')
            return redirect("/")
        if file and allowed_file(file.filename):
            url = "https://s3-%s.amazonaws.com/%s/%s" % (app.config['S3_REGION'], app.config['S3_BUCKETNAME'], file.filename)
            bucket.put_object(Body=file,
                          Key=file.filename,
                          ACL='public-read',
                          ContentType=file.content_type)
            data = request.form.to_dict()
            qry = "INSERT INTO `posts` (`title`, `quote`, `image_url`) VALUES ('{}', '{}', '{}')".format(data['title'],data['quote'],url)

            mydb = mysql.connector.connect(
              host=app.config['RDS_ENDPOINT'],
              user=app.config['RDS_USER'],
              passwd=app.config['RDS_PASSWORD'],
              database="awsdb"
            )
            mydb.autocommit = True
            cursor = mydb.cursor()
            cursor.execute(qry)
            qry = "SELECT * FROM `posts`"
            cursor.execute(qry)
            print(cursor.fetchall())
            cursor.close()
            return redirect("/")


if __name__ == '__main__':
      app.run(host='0.0.0.0', port=80 ,debug=True)
