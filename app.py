import os
from datetime import datetime
from flask import Flask, redirect, render_template, request, session, url_for, jsonify
from classifier import MovieReviewClassifier
from user import User
from postgres_utils import UserDB, TokensDB, ActivityLogDB
import redis 


DEBUG_FLAG= os.getenv('debug', 'False')=='True'
app = Flask(__name__)

try:
    redis_host= os.environ.get('REDIS_HOST', 'localhost')
    print("redis_host is ", redis_host)
    redis_client = redis.StrictRedis(host=redis_host, port=6379, password="redis123", db=1)
    print("Connected to Redis! host = %s".format(redis_host))
except Exception as e:
    print(f"Error connecting to Redis: {e}")

auth = {
        'dbname' : 'sentiment_analyzer_db',
        'username' : os.environ.get('POSTGRES_USERNAME', 'root'),
        'password' : os.environ.get('POSTGRES_PASSWORD', 'root'),
        'host' : os.environ.get('POSTGRES_HOST', '0.0.0.0'),
        'port' : os.environ.get('POSTGRES_PORT', 5432)
    }
user_obj = UserDB(auth)
token_obj = TokensDB(auth)
activitylog_obj = ActivityLogDB(auth)

################################################################

@app.route('/', methods = ['GET'])
@app.route('/login_page', methods=['GET'])
def loginpage():
    return render_template('login.html')


@app.route('/login', methods=['GET'])
def login():
    username = request.args.get('loginUsername')
    password = request.args.get('loginPassword')
    print('~', username, password)
    if user_obj.validate_user(User(username, password)):
        print('Login successful')
        token = token_obj.generate_token(username=username)
        activitylog_obj.update_activity(username=username, activity='login')
        return render_template('index.html', token=token)
    else:
        print('Login failed')
        return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    username = request.args.get('regUsername')
    password = request.args.get('regPassword')
    if not username or not password:
        print('Both username and password are required')
    else:
        new_user = User(username=username, password=password)
        user_obj.insert_user(new_user)
    return render_template('login.html')


@app.route('/logout', methods=['GET'])
def logout():
    # TBD: delete the token from table if not needed anymore.
    return redirect(url_for('login.html'))


@app.route('/index', methods = ['GET'])
def home_page():
    token = request.args.get('token')
    if token_obj.verify_token(token):
        inference_response = request.args.get('inference_response')
        return render_template('index.html', token=token, inference_response=inference_response)
    else:
        print('Session Expired : Invalid token')
        return render_template('login.html')


@app.route('/train', methods = ['POST'])
def train():
    token = str(request.headers.get('Authorization'))
    username = token_obj.get_username(token)
    #print(token, token_obj.verify_token(token))
    if token_obj.verify_token(token):
        lock_key="training_lock"
        acquired_lock = redis_client.set(lock_key, 'locked', nx=True, ex=300)
        print("acquired_lock: ", acquired_lock)
        if acquired_lock:
            try:
                print("Training started")
                obj = MovieReviewClassifier()
                obj.train_data()
                result = 'Training completed'
                activitylog_obj.update_activity(username=username, activity='training')
            except Exception as e:
                result = f'Training failed with {e}'
            finally:
                # Release the lock
                redis_client.delete(lock_key)
        else:
            result = 'Training is already in progress'
            print("here", result, acquired_lock)
        return jsonify(status=result, token=token)
    else:
        print('Session Expired : Invalid token')
        return render_template('login.html')
    


@app.route('/infer', methods=['GET'])
def infer():
    token = str(request.args.get('token')) 
    username = token_obj.get_username(token)
    if token_obj.verify_token(token):
        try:
            query = request.args.get('query')
            print("Predicting your query : ", query)

            obj = MovieReviewClassifier()
            if query:
                result = f'{query} - {obj.infer(query)}'
                activitylog_obj.update_activity(username=username, activity='inference')
            else:
                result = "No query passed"
        except Exception as e:
            result = f"Exception : {e}"
        return redirect(url_for('home_page', inference_response=result, token=token))
    else:
        print('Session Expired : Invalid token')
        return render_template('login.html')

if __name__ == "__main__":
    print("starting the application")
    app.run(host="0.0.0.0", debug=True, port=5002)
