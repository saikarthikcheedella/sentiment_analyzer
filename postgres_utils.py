import os
import bcrypt
import base64
import datetime
from enum import Enum
from functools import wraps
import psycopg2
from psycopg2 import sql
from typing import Dict
import uuid

from user import User


VARCHAR_DEFAULT_SIZE = 100

class DatabaseCommunicationError(RuntimeError):
    """Error when trying to connect, query or communicate to the postgres database."""


class PostgresDBWrapper:
    def __init__(self, auth: Dict):
        """
        Creates connection based on database credentials.
        Args:
            auth (dict): Contains dbname, username, password, host, port            
        """
        try:
            self.connection = psycopg2.connect(
                dbname = auth['dbname'],
                user = auth['username'],
                password = auth['password'],
                host = auth['host'],
                port = auth['port']
            )
            self.cursor = self.connection.cursor()
        except Exception as e:
            print('Exception in establishing the connection : ', e)

    def execute_query(self, query, data=None, is_read=False) -> Dict:
        """
        Executes the given query and returns result if it's a read query.
        Args:
            query: query string to execute.
            data: dict containing parameters to run the query.
            is_read: boolen flag indicating if it's a read/write query.
        """
        try:
            self.cursor.execute(query, data)
            if is_read:
                return self.cursor.fetchall()
            self.connection.commit()
        except Exception as exc:
            print(exc)
            raise DatabaseCommunicationError('Failed to execute the query') from exc
        if is_read: return None 

    def close_connection(self):
        self.cursor.close()
        self.connection.close()


class Hashing:
    def __init__(self, password):
        self.password = password.encode('utf-8')
        self.encrypted_pwd = self.encrypt()

    def encrypt(self):
        salt = bcrypt.gensalt()
        encrypted_pwd = bcrypt.hashpw(self.password, salt)
        encrypted_pwd = base64.b64encode(encrypted_pwd).decode('utf-8')
        return encrypted_pwd


class UserDBColumns(Enum):
    USERNAME = sql.Identifier('username')
    PASSWORD = sql.Identifier('password')

class UserDB(PostgresDBWrapper):
    def __init__(self, auth: Dict):
        super().__init__(auth=auth)
        self.table_name = 'USER'
        self.create_table()

    def create_table(self):
        # Creating table
        create_table_query = sql.SQL(
                'CREATE TABLE IF NOT EXISTS {table_name}'
                f' ({{username_col}} VARCHAR({VARCHAR_DEFAULT_SIZE}) PRIMARY KEY,'
                f' {{password_col}} VARCHAR({VARCHAR_DEFAULT_SIZE}) NOT NULL)'
            ).format(
                table_name=sql.Identifier(self.table_name),
                username_col=UserDBColumns.USERNAME.value,
                password_col=UserDBColumns.PASSWORD.value
            )
        self.execute_query(create_table_query)
        print("Executed successfully")

    def insert_user(self, user: User):
        """
        Inserts record into USER table.
        Args: 
            user: User class object holding username & password info.
        """
        try:
            insert_user_query = sql.SQL(
                    'INSERT INTO {table_name} ({username_col}, {password_col}) '
                    'VALUES ({username}, {password})'
                ).format(
                    table_name=sql.Identifier(self.table_name),
                    username_col=UserDBColumns.USERNAME.value,
                    password_col=UserDBColumns.PASSWORD.value,
                    username=sql.Literal(user.username),
                    password=sql.Literal(Hashing(user.password).encrypted_pwd)
                )
            self.execute_query(insert_user_query)
            print("Insertion successful")
        except psycopg2.errors.UniqueViolation:
            print("Insertion failed: User already exists")
        except: 
            print("Insertion failed")

    
    def delete_user(self, user: User):
        """
        Deletes record from USER table.
        Args: 
            user: User class object holding username & password info.
        """
        delete_user_query = sql.SQL(
                'DELETE FROM {table_name} where '
                '{username_col} = {username}'
            ).format(
                table_name=sql.Identifier(self.table_name),
                username_col=UserDBColumns.USERNAME.value,
                username=sql.Literal(user.username)
            )
        self.execute_query(delete_user_query)
        print("Deletion successful")

    def validate_user(self, user):
        """
        Validates user details and returns True or False upon validating them
        Args:
            user: User class object holding username & password info.
        """
        try:
            get_user_query = sql.SQL(
                    'SELECT * FROM {table_name} where '
                    '{username_col} = {username} '
                ).format(
                    table_name=sql.Identifier(self.table_name),
                    username_col=UserDBColumns.USERNAME.value,
                    username=sql.Literal(user.username)
                )
            result = self.execute_query(get_user_query, is_read=True)
            print("res : ", result)
            stored_hash_bytes=None
            if result:
                result = result[0]
                stored_username = result[0]
                stored_hash_bytes = base64.b64decode(result[1])
            is_pwd_valid = bcrypt.checkpw(user.password.encode('utf-8'), stored_hash_bytes)
            if user.username == stored_username and is_pwd_valid:
                return True
        except:
            return False
        return False

    def delete_user(self, user):
        """
        Deletes user from table
        Args:
            user: User class object holding username & password info.
        """
        delete_user_query = sql.SQL(
                'DELETE FROM {table_name} where '
                '{username_col} = {username} '
            ).format(
                table_name=sql.Identifier(self.table_name),
                username_col=UserDBColumns.USERNAME.value,
                username=sql.Literal(user.username)
            )
        self.execute_query(delete_user_query)
        

class TokensDBColumns(Enum):
    TOKEN_ID = sql.Identifier('token_id')
    USERNAME = sql.Identifier('username')
    TOKEN = sql.Identifier('token')
    CREATED_AT = sql.Identifier('created_at')
    EXPIRES_AT = sql.Identifier('expires_at')

class TokensDB(PostgresDBWrapper):
    def __init__(self, auth: Dict):
        super().__init__(auth=auth)
        self.table_name = 'TOKENS'
        self.create_table()

    def create_table(self):
        # Creating table
        create_table_query = sql.SQL(
                'CREATE TABLE IF NOT EXISTS {table_name}'
                f' ({{tokenid_col}} SERIAL PRIMARY KEY,'
                f' {{username_col}} VARCHAR({VARCHAR_DEFAULT_SIZE}) NOT NULL,'
                f' {{token_col}} VARCHAR({VARCHAR_DEFAULT_SIZE}) NOT NULL,'
                f' {{created_at_col}}  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,'
                f' {{expires_at_col}} TIMESTAMP NOT NULL )'
            ).format(
                table_name=sql.Identifier(self.table_name),
                tokenid_col=TokensDBColumns.TOKEN_ID.value,
                username_col=TokensDBColumns.USERNAME.value,
                token_col=TokensDBColumns.TOKEN.value,
                created_at_col=TokensDBColumns.CREATED_AT.value,
                expires_at_col=TokensDBColumns.EXPIRES_AT.value
            )
        self.execute_query(create_table_query)
        print("Executed successfully")

    def generate_token(self, username):
        """
        Generates a unique token, inserts it into table & returns it.
        Args:
            username: a string, username
        """
        token = uuid.uuid4().hex
        insert_token_query = sql.SQL(
                'INSERT INTO {table_name} ({username_col}, {token_col}, {created_at_col}, {expires_at_col}) '
                'VALUES ({username}, {token}, {created_at}, {expires_at})'
            ).format(
                table_name=sql.Identifier(self.table_name),
                username_col=TokensDBColumns.USERNAME.value,
                token_col=TokensDBColumns.TOKEN.value,
                created_at_col=TokensDBColumns.CREATED_AT.value,
                expires_at_col=TokensDBColumns.EXPIRES_AT.value,
                username=sql.Literal(username),
                token=sql.Literal(token),
                created_at=sql.Literal(datetime.datetime.now()),
                expires_at=sql.Literal(datetime.datetime.now() + datetime.timedelta(days=1))
            )
        self.execute_query(insert_token_query)
        return token

    def get_username(self, token: str):
        """
        Returns username for a given token
        Args:
            token: a string type token.
        """
        try:
            get_username_query = sql.SQL(
                    'SELECT {username_col} FROM {table_name} where '
                    '{token_col} = {token}'
                ).format(
                    username_col=TokensDBColumns.USERNAME.value,
                    table_name=sql.Identifier(self.table_name),
                    token_col=TokensDBColumns.TOKEN.value,
                    token=sql.Literal(token)
                )
            result = self.execute_query(get_username_query, is_read=True)
            print('res : ', result)
            if result:
                return result[0]
        except: 
            print("unable to get the username!")
            return ''
        return ''

    def verify_token(self, token: str):
        """
        Validates if the token is still exists and valid.
        Args:
            token: a string type token 
        """
        try:
            exp_time = datetime.datetime.now()
            get_token_query = sql.SQL(
                    'SELECT * FROM {table_name} where '
                    '{token_col} = {token} AND '
                    '{expires_at_col} > {expires_at}'
                ).format(
                    table_name=sql.Identifier(self.table_name),
                    token_col=TokensDBColumns.TOKEN.value,
                    expires_at_col=TokensDBColumns.EXPIRES_AT.value,
                    token=sql.Literal(token),
                    expires_at=sql.Literal(exp_time)
                )
            result = self.execute_query(get_token_query, is_read=True)
            print("res : ", result)
            if result:
                return True
        except: 
            return False
        return False

    def invalidate_token(self, token):
        """
        Delete the token from the table
        Args:
            token: a string based token
        """
        delete_token_query = sql.SQL(
                'DELETE FROM {table_name} where '
                '{token_col} = {token}'
            ).format(
                table_name=sql.Identifier(self.table_name),
                token_col=TokensDBColumns.TOKEN.value,
                token=sql.Literal(token)
            )
        self.execute_query(delete_token_query)



class ActivityLogDBColumns(Enum):
    USERNAME = sql.Identifier('username')
    LAST_LOGIN = sql.Identifier('last_login')
    LAST_TRAINING = sql.Identifier('last_training')
    LAST_INFERENCE = sql.Identifier('last_inference')

class ActivityLogDB(PostgresDBWrapper):
    def __init__(self, auth: Dict):
        super().__init__(auth=auth)
        self.table_name = 'ACTIVITY_LOG'
        self.create_table()

    def create_table(self):
        # Creating table
        create_table_query = sql.SQL(
                'CREATE TABLE IF NOT EXISTS {table_name} ('
                f' {{username_col}} VARCHAR({VARCHAR_DEFAULT_SIZE}) NOT NULL UNIQUE,'
                f' {{last_login_col}} TIMESTAMP,'
                f' {{last_training_col}} TIMESTAMP,'
                f' {{last_inference_col}} TIMESTAMP)'
            ).format(
                table_name=sql.Identifier(self.table_name),
                username_col=ActivityLogDBColumns.USERNAME.value,
                last_login_col=ActivityLogDBColumns.LAST_LOGIN.value,
                last_training_col=ActivityLogDBColumns.LAST_TRAINING.value,
                last_inference_col=ActivityLogDBColumns.LAST_INFERENCE.value
            )
        self.execute_query(create_table_query)
        print("Executed successfully")

    def update_activity(self, username: str, activity: str):
        """
        update the activity table column.
        Args:
            username: a string, username
            action: a string , training/inference.
        """
        if activity is 'login':
            activity_col = ActivityLogDBColumns.LAST_LOGIN.value
        if activity is 'training':
            activity_col = ActivityLogDBColumns.LAST_TRAINING.value
        elif activity is 'inference':
            activity_col = ActivityLogDBColumns.LAST_INFERENCE.value

        update_action_query = sql.SQL(
            'INSERT INTO {table_name} ({username_col}, {activity_col}) '
            'VALUES ({username}, {activity_time}) '
            'ON CONFLICT ({username_col}) DO UPDATE '
            'SET {activity_col} = {activity_time}'
        ).format(
            table_name=sql.Identifier(self.table_name),
            username_col=ActivityLogDBColumns.USERNAME.value,
            activity_col=activity_col,
            username=sql.Literal(username),
            activity_time=sql.Literal(datetime.datetime.now())
        )
        self.execute_query(update_action_query)
        print("Activity updated successfully")





# if __name__== '__main__':
#     auth = {
#         'dbname' : 'flask_db',
#         'username' : 'root',
#         'password' : 'root',
#         'host' : 'localhost',
#         'port' : 5432
#     }
    # try:
        # u = UserDB(auth)
        # print("No errors while establishing conneciton")
        # print(u.create_table())
        # new_user = User('SAI', '12345')
        # #print(u.insert_user(new_user))
        # print("="*20, "started validating user ", "="*20)
        # print(u.validate_user(new_user))
        # #print(u.delete_user(new_user))

    #     t= TokensDB(auth)
    #     x = t.generate_token('SAI')
    #     print(x)
    #     t.verify_token(x)
    #     t.invalidate_token(x)
    # except Exception as e:
    #     print("errors while connecting : ", e)
    
    

# TBD:
# clean up unused tokens
# clean up Activity log data periodically