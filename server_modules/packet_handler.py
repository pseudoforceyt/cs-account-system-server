import uuid as UUID
import asyncio
import pickle
from . import encryption as en
from . import db_handler as db
from cryptography.hazmat.primitives import serialization as s
from captcha.image import ImageCaptcha
from random import randint
import datetime

async def identify_client(websocket, SESSIONS):
    return list(SESSIONS.keys())[[i[0] for i in list(SESSIONS.values())].index(websocket)]

async def disconnect(ws, code, reason):
    print(f"[INFO] CLIENT {ws.remote_address} DISCONNECTED due to",code,reason)
    await ws.close(code=code, reason=reason)
    return 'CONN_CLOSED'

#async def get_packet(ws, type):
#    # packet validator
def parse_date(date_string):
    date_formats = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"]

    for date_format in date_formats:
        try:
            date_obj = datetime.datetime.strptime(date_string, date_format)
        except ValueError:
            pass
        else:
            return date_obj
    else:
        return 'PARSE_ERR'

def parse_time(time_string):
    try:
        time_obj = datetime.datetime.strptime(time_string, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return 'PARSE_ERR'
    else:
        return 'VALID_TIME'
    

async def establish_conn(SESSIONS, SERVER_CREDS, ws):
    print(f"[INFO] Remote {ws.remote_address} attempted connection")
    uuid = str(UUID.uuid4())
    SESSIONS[uuid] = [ws, None, None] # ws, public_key, user_uuid

    print(f"[INFO] Remote {ws.remote_address} initiated connection with UUID: {uuid}")
    print(f"[INFO] Sending public key to {uuid}")

    # Encrypt Connection
    await ws.send(pickle.dumps({'type':'CONN_ENCRYPT_S','data':SERVER_CREDS['server_epbkey']}))
    try:
        client_epbkey = pickle.loads(await ws.recv())
        try:
            client_epbkey = s.load_pem_public_key(client_epbkey['data'])
        except Exception as e:
            print(f"[INFO] Client un-established {ws.remote_address} DISCONNECTED due to INVALID_PACKET")
            await ws.close(code = 1008, reason = "Invalid packet structure")
            return 'CONN_CLOSED'
        
        SESSIONS[uuid][1] = client_epbkey
        print(f"[INFO] Received public key for {uuid}")
        del client_epbkey
        return en.encrypt_packet(
            {'type':'STATUS', 'data':{'sig':'CONN_OK'}},
            SESSIONS[uuid][1],
            )
    # If client sends bullshit instead of its PEM serialized ephemeral public key
    except Exception as err2:
        print(f"[INFO] CLIENT {uuid} {ws.remote_address} DISCONNECTED due to INVALID_CONN_KEY:\n\t",err2)
        await ws.close(code = 1003, reason = "Connection Public Key in invalid format")
        del SESSIONS[uuid]
        return 'CONN_CLOSED'
    
async def get_resp_packet(SESSIONS, ws, de_packet):
    uuid = await identify_client(ws, SESSIONS)
    en_packet = en.encrypt_packet(de_packet, SESSIONS[uuid][1])
    return en_packet

async def send_user_packet(SESSIONS, SERVER_CREDS, user_uuid, de_packet):
    try:
        con_uuid = list(SESSIONS.keys())[[i[2] for i in list(SESSIONS.values())].index(user_uuid)]
        ws = SESSIONS[con_uuid][0]
        ws.send(en.encrypt_packet(de_packet, SESSIONS[con_uuid[1]]))
    except Exception as ear:
        print("[DEBUG] Queued Packet for", user_uuid, "due to:\n\t", ear)
        db.queue_packet(user_uuid, en.encrypt_packet(de_packet, SERVER_CREDS['queue_pubkey']))

async def signup(SESSIONS, SERVER_CREDS, ws, data):
    uuid = list(SESSIONS.keys())[[i[0] for i in list(SESSIONS.values())].index(ws)]
    try:
        user = data['user']
        email = data['email']
        fullname = data['fullname']
        dob = parse_date(data['dob'])
        password = data['password']
    except KeyError as ero:
        return await get_resp_packet(SESSIONS, ws, {'type':'STATUS','data':{'sig':'SIGNUP_MISSING_CREDS','desc':ero}})
    # Define validation rules
    validation_rules = [
        (len(user) > 32, 'SIGNUP_USERNAME_ABOVE_LIMIT'),
        (db.check_if_exists(user, 'username'), 'SIGNUP_USERNAME_ALREADY_EXISTS'),
        (len(email) > 256, 'SIGNUP_EMAIL_ABOVE_LIMIT'),
        (len(fullname) > 256, 'SIGNUP_NAME_ABOVE_LIMIT'),
        (dob == 'PARSE_ERR', 'SIGNUP_DOB_INVALID'),
        (len(password) > 384, 'SIGNUP_PASSWORD_ABOVE_LIMIT')
    ]
    # Validate user input
    for condition, error_message in validation_rules:
        if condition:
            return await get_resp_packet(SESSIONS, ws, {'type':'STATUS','data':{'sig':error_message}})
    resp_captcha = await captcha(SESSIONS, SERVER_CREDS, ws, data)
    if resp_captcha == True:
        print(f"[INFO] CLIENT {uuid} ATTEMPTED SIGNUP WITH username {user}")
        salted_pwd = en.salt_pwd(password)
        try:
            db.Account.create(user, fullname, dob, email, salted_pwd)
        except Exception as errr:
            return await get_resp_packet(SESSIONS, ws, {'type':'STATUS','data':{'sig':'SIGNUP_ERR','desc':errr}})
        else:
            return await get_resp_packet(SESSIONS, ws, {'type':'STATUS','data':{'sig':'SIGNUP_OK'}})
    elif resp_captcha == False:
        return await get_resp_packet(SESSIONS, ws, {'type':'STATUS','data':{'sig':'CAPTCHA_WRONG'}})

async def login(SESSIONS, SERVER_CREDS, ws, data):
    try:
        identifier = data['id']
        password = data['password']
        dont_ask_again = data['save']
    except KeyError as ero:
        return await get_resp_packet(SESSIONS, ws, {'type':'STATUS','data':{'sig':'LOGIN_MISSING_CREDS','desc':ero}})
    resp_captcha = await captcha(SESSIONS, SERVER_CREDS, ws, data)
    if resp_captcha == True:
        flag, uuid = db.Account.check_pwd(password, identifier)
        if flag == True:
            if dont_ask_again == True:
                secret, access_token = en.gen_token(uuid, 30)
            else:
                secret, access_token = en.gen_token(uuid, 1)
            db.Account.set_token(uuid, secret)
            en_packet = await get_resp_packet(SESSIONS, ws, {'type':'TOKEN_GEN','data':{'token':access_token}})
            print("[INFO] Generated token for", uuid)
            return en_packet
        elif flag == False:
            return await get_resp_packet(SESSIONS, ws, {'type':'STATUS','data':{'sig':'LOGIN_INCORRECT_PASSWORD'}})
        elif flag == 'ACCOUNT_DNE':
            return await get_resp_packet(SESSIONS, ws, {'type':'STATUS','data':{'sig':'LOGIN_ACCOUNT_NOT_FOUND'}})
    elif resp_captcha == False:
        return await get_resp_packet(SESSIONS, ws, {'type':'STATUS','data':{'sig':'CAPTCHA_WRONG'}})

async def auth(SESSIONS, SERVER_CREDS, ws, data):
    # REMINDER TO HANDLE LOGIN FROM TWO DEVICES
    user = data['user']
    token = data['token']
    con_uuid = await identify_client(ws, SESSIONS)
    user_uuid = db.get_uuid(user)
    if user_uuid == 'ACCOUNT_DNE':
        return await get_resp_packet(SESSIONS, ws, {'type':'STATUS','data':{'sig':'ACCOUNT_DNE'}})
    key = db.Account.get_token_key(user_uuid)
    if key == 'TOKEN_NOT_FOUND':
        return await get_resp_packet(SESSIONS, ws, {'type':'STATUS','data':{'sig':'TOKEN_NOT_FOUND'}})
    flag = en.validate_token(key, token, user_uuid)
    if flag == 'TOKEN_OK':
        SESSIONS[con_uuid][2] = user_uuid
        # tasks to run on login
        print("[INFO] User", user_uuid, "logged in from", ws.remote_address)
        print("[DEBUG] SESSIONS:", SESSIONS)
        return await get_resp_packet(SESSIONS, ws, {'type':'STATUS','data':{'sig':'LOGIN_OK'}})
    elif flag == 'TOKEN_EXPIRED':
        return await get_resp_packet(SESSIONS, ws, {'type':'STATUS','data':{'sig':'TOKEN_EXPIRED'}})
    elif flag == 'TOKEN_INVALID':
        return await get_resp_packet(SESSIONS, ws, {'type':'STATUS','data':{'sig':'TOKEN_INVALID'}})

async def logout(SESSIONS, SERVER_CREDS, ws, data):
    sender = await identify_client(ws, SESSIONS)
    user = SESSIONS[sender][2]
    if not user:
        return await get_resp_packet(SESSIONS, ws, {'type':'STATUS','data':{'sig':'NOT_LOGGED_IN'}})
    flag = db.Account.logout(user)
    if flag == 'SUCCESS':
        SESSIONS[sender][2] = None
        print("[DEBUG] SESSIONS:", SESSIONS)
        return await get_resp_packet(SESSIONS, ws, {'type':'STATUS','data':{'sig':'LOGOUT_OK'}})
    elif flag == 'FAILURE':
        return await get_resp_packet(SESSIONS, ws, {'type':'STATUS','data':{'sig':'LOGOUT_ERR'}})

async def captcha(SESSIONS, SERVER_CREDS, ws, data):
    uuid = await identify_client(ws, SESSIONS)
    challenge = str(randint(100000,999999))
    data = ImageCaptcha().generate(challenge)
    image = data.getvalue()

    packet = en.encrypt_packet({'type':'CAPTCHA', 'data':{'challenge':image}}, SESSIONS[uuid][1])
    await ws.send(packet)
    print(f"[INFO] GENERATED CAPTCHA FOR CLIENT {uuid} with CODE {challenge}")
    resp = await ws.recv()

    # handle possible INVALID_PACKET in next line 
    de_resp = en.decrypt_packet(resp, SERVER_CREDS['server_eprkey'])
    de_resp = de_resp['data']['solved']
    return int(de_resp) == int(challenge)

upacket_map = {
    'CONN_INIT':1,
    'CONN_ENCRYPT_C':2
}
packet_map = {
    'SIGNUP':signup,
    'LOGIN':login,
    'AUTH_TOKEN':auth,
    'LOGOUT':logout
}

async def handle(SESSIONS, SERVER_CREDS, packet, ws):
    if 'type'.encode() in packet:
        de_packet = pickle.loads(packet)
    else:
        de_packet = en.decrypt_packet(packet, SERVER_CREDS['server_eprkey'])
    if de_packet['type'] == 'INVALID_PACKET':
        await disconnect(ws, 1008, "Invalid Packet Structure")
        return 'CONN_CLOSED'
    else:
        type = de_packet['type']
        data = de_packet['data']

    if type == 'CONN_INIT':
        return await establish_conn(SESSIONS, SERVER_CREDS, ws)
    elif type in packet_map.keys():
        func = packet_map[type]
        return await func(SESSIONS, SERVER_CREDS, ws, data)
    else:
        await disconnect(ws, 1008, "Invalid Packet Structure")
        return 'CONN_CLOSED'

