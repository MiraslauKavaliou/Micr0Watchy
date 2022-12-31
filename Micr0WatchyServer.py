# APIs
import spotipy, pyowm
# Networking
import http.server, socketserver, requests, json, ssl
# Other
import time, threading, os, dotenv

# Load .env
dotenv.load_dotenv()

# <ALL USER INFO IS IN THE .env FILE>

# Your OpenWeather API Key
owm = pyowm.OWM(os.getenv('OPENWEATHER_KEY'))
mgr = owm.weather_manager()

city = os.getenv('OPENWEATHER_CITY')

# Your client ID and client secret
client_id = os.getenv('SP_CLIENT_ID')
client_secret = os.getenv('SP_CLIENT_SECRET')

# Your Spotify username
username = os.getenv('SP_USERNAME')

keyPass = os.getenv('KEY_PASSWD')

# Redirect uri for spotify authentication
redirect_uri = "http://"+os.getenv('HOST_IP')+":18723/"

# <ALL USER INFO IS IN THE .env FILE>

# Get path of project directory
path = os.path.dirname(__file__)+"/"

# --- Redirect Server for spotify authorization ---

def redirectServer():
    PORT = 18723

    Handler = http.server.SimpleHTTPRequestHandler
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print("serving at port", PORT, end="")
        print("... Success!")
        httpd.serve_forever()

print("Starting Redirect Server, ", end="")

# Create a new thread to run the loop
redserverthread = threading.Thread(target=redirectServer)

# Start the thread
redserverthread.start()

time.sleep(1)



# Get an access token and refresh token
scope = "user-read-currently-playing user-read-playback-state user-modify-playback-state"

oauth = spotipy.oauth2.SpotifyOAuth(client_id, client_secret, redirect_uri, scope=scope, username=username)
auth_url = oauth.get_authorize_url()


# Check for cached tokens, if none then ask user to authenticate
try:
    token_info = oauth.get_cached_token()
    if (token_info["expires_at"]-int(time.time()) <= 0):
        raise TypeError
except TypeError:
    # Redirect the user to the authorization URL
    print("Please go to the following URL and grant access to your Spotify account:")
    print(auth_url)
    # Wait for the user to grant access
    try:
        input("Press Enter after granting access:")
    except EOFError:
        pass

# Get the access token and refresh token
access_token = oauth.get_access_token(as_dict=False)
sp = spotipy.Spotify(auth=access_token)

# --- Spotify Token Refresh Loop ---
def tokenloop():
    global sp, access_token
    reftime = 0
    time.sleep(1)
    while True:
        print("Refreshing Token...", end="")
        token_info = oauth.get_cached_token()
        reftime = token_info["expires_at"]-int(time.time())-200
        refresh_token = token_info["refresh_token"]
        oauth.refresh_access_token(refresh_token)
        access_token = oauth.get_cached_token()["access_token"]
        sp = spotipy.Spotify(auth=access_token)
        print(" Success! Next refresh in "+str(reftime)+" seconds.")
        time.sleep(reftime)

# <--- Info Collection --->

infoDict = {
    "name":"NA",
    "artists":"NA",
    "isPlaying":False,
    "temperature":0,
    "status":"NA",
    "spresponsecode":503,
    "wtresponsecode":503
}

# --- Spotify Loop ---

def spotifyloop():
    while True:
        tmpname = str(infoDict["name"])
        tmpartists = str(infoDict["artists"])
        tmpisPlaying = bool(infoDict["isPlaying"])
        
        try:
            current_song = sp.current_playback()
            infoDict["isPlaying"] = current_song['is_playing']
            infoDict["name"] = str(current_song['item']['name'])
            infoDict["artists"] = str(current_song['item']['artists'][0]['name'])
            for artist in current_song['item']['artists'][1:]:
                infoDict["artists"]+=", "+str(artist['name'])
            infoDict["spresponsecode"] = 200
        except TypeError:
            infoDict["name"] = tmpname
            infoDict["artists"] = tmpartists
            infoDict["isPlaying"] = tmpisPlaying
        except requests.exceptions.ReadTimeout:
            print("Timed Out...")
            infoDict["spresponsecode"] = 504
        except spotipy.client.SpotifyException:
            print("SpotifyException, Most likely expired token")
            infoDict["spresponsecode"] = 502
        except requests.exceptions.ConnectionError:
            print("ConnectionError")
            infoDict["spresponsecode"] = 503
        except Exception as e:
            infoDict["spresponsecode"] = 500
            print(e)


        # if (tmpname != infoDict["name"] or tmpartists != infoDict["artists"]):
        #     print("Name: " + infoDict["name"])
        #     print("Artist: " + infoDict["artists"])
        # if (tmpisPlaying != infoDict["isPlaying"]):
        #     print(infoDict["isPlaying"])
        time.sleep(0.5)

# --- OpenWeather Fetcher Loop ---

def weatherloop():
    while True:
        print("Getting Weather in "+city+"...", end="")
        try:
            observation = mgr.weather_at_place(city)
            w = observation.weather
            infoDict["temperature"] = round(w.temperature('celsius')['temp'])
            infoDict["status"] = w.detailed_status.title()
            infoDict["wtresponsecode"] = 200
            print(" Success!")
        except Exception as e:
            infoDict["wtresponsecode"] = 500
            print(e)

        # # Print the temperature and status
        # print("Temperature: "+str(infoDict["temperature"])+"°C")
        # print("Status: "+str(infoDict["status"]))
        
        time.sleep(60*10) # 10 minutes in seconds
        
# --- Starting threads ---

# Create a new thread to run the loop
tokenthread = threading.Thread(target=tokenloop)
# Start the thread
tokenthread.start()

sptthread = threading.Thread(target=spotifyloop)
sptthread.start()

weatherthread = threading.Thread(target=weatherloop)
weatherthread.start()

# --- RequestHandler Server ---

class RequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Set the response code to 200 OK
        self.send_response(200)
        
        # Set the content type to application/json
        self.send_header('Content-type', 'application/json')
        
        # Set the Content-Security-Policy header to allow loading resources over HTTPS
        self.send_header('Content-Security-Policy', "default-src https:")
        
        # End the headers
        self.end_headers()
        
        # Convert the dictionary to a JSON string
        json_data = json.dumps(infoDict)
        
        # Write the JSON string to the response body
        self.wfile.write(bytes(json_data, 'utf-8'))

    def do_POST(self):
        self.send_response(200)

        self.send_header('Content-type', 'application/json')
        
        # Set the Content-Security-Policy header to allow loading resources over HTTPS
        self.send_header('Content-Security-Policy', "default-src https:")
        
        # End the headers
        self.end_headers()

        # Read the request body
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)

        # Convert the request body to a JSON object
        data = json.loads(body)

        # Check the value of the "command" field
        if data["command"] == "next":
            sp.next_track()
        elif data["command"] == "prev":
            sp.previous_track()
        elif data["command"] == "pause":
            if infoDict["isPlaying"]:
                sp.start_playback()
            else:
                sp.pause_playback()
        else:
            return
        

def getServer():
    PORT = 18724

    # Create a SSL context
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    
    # Load the SSL certificate and key
    context.load_cert_chain(certfile=path+'certificate.pem', keyfile=path+'key.pem', password=keyPass)

    # Create the server and handler objects
    server = socketserver.TCPServer(("", PORT), RequestHandler)

    # Wrap the server in the SSL context
    server.socket = context.wrap_socket(server.socket, server_side=True)

    print("serving at port", PORT, end="")
    print("... Success!")
    # Start the server loop
    server.serve_forever()
    
time.sleep(2)

print("Starting Request Handler Server, ", end="")

# Create a new thread to run the loop
getserverthread = threading.Thread(target=getServer)

# Start the thread
getserverthread.start()