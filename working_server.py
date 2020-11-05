#!/usr/bin/env python3

import datetime
import logging
import asyncio
import aiocoap.resource as resource
import aiohttp_cors
import aiocoap
import datetime
import aiomysql
import json
import ast
import random
from aiohttp import web
import database

# define global variable to store LedResource instance to call its notify function
# cant use the class instance directly as it has to be initialized in a server context
led_resource = None
# same for number of observers
obs_count = 0


async def processData(data):
    opts = ['TEMP', 'HUMID', 'AIR_PRESS']
    data = ast.literal_eval(data) # allows to parse json with single quotes
    if data["appId"] and data["appId"] in opts:
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = 'INSERT INTO `db`.`{}` (`value`, `time`) VALUES ({}, "{}")'.format(data["appId"].lower(), data["data"], date)
        conn = http_app['db']
        print(query)
        await database.DBConnector(conn).execute(query)

# connects to db, saves a connector to the http app dict
async def init_db(app, loop):
    connection = await aiomysql.create_pool(
        host='localhost',# db',
        user='root',
        password='1324',
        db='db',
        loop=loop)
    if connection:
        print("got database connection:" + str(connection))
    app['db'] = connection

# creates all tables necessary for this application if not yet present
async def setup_db(app):
    conn = await app['db'].acquire()
    cur = await conn.cursor()
    try:
        queries = []
        queries.append('''CREATE TABLE `temp` (
          `id` int(11) NOT NULL AUTO_INCREMENT,
          `celcius` float DEFAULT NULL,
          `time` datetime DEFAULT NULL,
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;''')
        # queries.append('''CREATE TABLE `humidity` (
        #   `id` int(11) NOT NULL AUTO_INCREMENT,
        #   `celcius` float DEFAULT NULL,
        #   `time` datetime DEFAULT NULL,
        #   PRIMARY KEY (`id`)
        # ) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;''')
        # queries.append('''CREATE TABLE `temperature` (
        #   `id` int(11) NOT NULL AUTO_INCREMENT,
        #   `celcius` float DEFAULT NULL,
        #   `time` datetime DEFAULT NULL,
        #   PRIMARY KEY (`id`)
        # ) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;''')
        # queries.append('''CREATE TABLE `temperature` (
        #   `id` int(11) NOT NULL AUTO_INCREMENT,
        #   `celcius` float DEFAULT NULL,
        #   `time` datetime DEFAULT NULL,
        #   PRIMARY KEY (`id`)
        # ) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;''')
        # queries.append('''CREATE TABLE `temperature` (
        #   `id` int(11) NOT NULL AUTO_INCREMENT,
        #   `celcius` float DEFAULT NULL,
        #   `time` datetime DEFAULT NULL,
        #   PRIMARY KEY (`id`)
        # ) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;''')


        for query in queries:
            await cur.execute(query)
        await self.connector.commit()
        await cur.close()
    except:
        return

# uses runners to run http site. Setup to add more http apps
runners = []
async def start_site(app, port, address='0.0.0.0'):
    runner = web.AppRunner(app)
    runners.append(runner)
    await runner.setup()
    site = web.TCPSite(runner, address, port)
    await site.start()

# returns static file with a websocket to poll data / send data
async def index(request):
    return web.FileResponse('./static/index.html')

# response is wether thingy is observing
async def thingy_status(request):
    return web.json_response({"online": obs_count > 0})

# receives hexcolor, notifies ledResource (ObservableResource)
async def update_led(request):
    color = request.match_info.get('hexcolor')
    led_resource.notify(color)
    return web.json_response({'color': color})

async def get_measurment(request):
    type = request.match_info.get('measurement')
    conn = request.app['db']
    print("GOT REQUEST, trying to access data")
    data = await database.DBConnector(conn).fetchall(type)
    print(data)
    return web.json_response(data)


# COAP SERVER =============================================
class CustomResource(resource.Resource):
    def __init__(self):
        super().__init__()
        self.set_content("ok, works---\n")

    def set_content(self, content):
        self.content = content

    # async def render_get(self, request):
    #     print("woow, cool i received a GET request")
    #     return aiocoap.Message(payload=self.content)

    async def render_put(self, request):
        print("UGLY PRINT")
        print(request.payload)
        print('===== PUT payload: %s' % request.payload.decode('ascii'))
        await processData(request.payload.decode('ascii'))
        self.set_content( request.payload )
        return aiocoap.Message(code=aiocoap.CHANGED, payload=self.content)

class LedResource(resource.ObservableResource):
    """Example resource that can be observed. The `notify` method keeps
    scheduling itself, and calles `update_state` to trigger sending
    notifications."""

    def __init__(self):
        super().__init__()
        # save this resource to global variable to be able to call notify
        # method from http server
        global led_resource
        led_resource = self

        # set default color red
        self.color = "ff0000"

    def update_observation_count(self, newcount):
        print("UPDATING GLOBAL obs count to: " + str(newcount))
        global obs_count
        obs_count = newcount

    # called with the updated color, updates state and notifies observers
    def notify(self, color):
        self.color = color
        self.updated_state()

    # render observe resource, get rendered on every state update (notify())
    async def render_get(self, request):
        print("rendering get with COLOR:")
        print(self.color)
        payload = ("{\"appId\":\"LED\",\"data\":{\"color\":\"" + self.color + "\"},\"messageType\":\"CFG_SET\"}").encode("ascii")
        # payload = datetime.datetime.now().strftime("%Y-%m-%d %H:%M").encode('ascii')
        return aiocoap.Message(payload=payload)

# used for testing, works
class TimeResource(resource.ObservableResource):
    """Example resource that can be observed. The `notify` method keeps
    scheduling itself, and calles `update_state` to trigger sending
    notifications."""

    def __init__(self):
        super().__init__()

        self.handle = None

    def notify(self):
        self.updated_state()
        self.reschedule()

    def reschedule(self):
        self.handle = asyncio.get_event_loop().call_later(5, self.notify)

    def update_observation_count(self, count):
        if count and self.handle is None:
            print("Starting the clock")
            self.reschedule()
        if count == 0 and self.handle:
            print("Stopping the clock")
            self.handle.cancel()
            self.handle = None

    async def render_get(self, request):
        payload = datetime.datetime.now().\
                strftime("%Y-%m-%d %H:%M").encode('ascii')
        return aiocoap.Message(payload=payload)

# logging setup
logging.basicConfig(level=logging.INFO)
logging.getLogger("coap-server").setLevel(logging.DEBUG)

# setup http app
http_app = web.Application()

# Configure default CORS settings.
cors = aiohttp_cors.setup(http_app, defaults={
    "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods="*",
        )
})

cors.add(http_app.router.add_get('/', index))
cors.add(http_app.router.add_get('/update_led/{hexcolor}', update_led))
cors.add(http_app.router.add_get('/measurement/{measurement}', get_measurment))
cors.add(http_app.router.add_get('/thingy_status', thingy_status))


# setup event loop for http
loop = asyncio.get_event_loop()
loop.run_until_complete(init_db(http_app, loop))
loop.run_until_complete(setup_db(http_app))

# create http site task
loop.create_task(start_site(http_app, port=4100))

# setup coap server
root = resource.Site()
root.add_resource(['.well-known', 'core'],
        resource.WKCResource(root.get_resources_as_linkheader))
root.add_resource(['testing'], CustomResource())
root.add_resource(['led'], LedResource())
root.add_resource(['time'], TimeResource())

# creates a context to all addresses on the default coap port
asyncio.Task(aiocoap.Context.create_server_context(root))

try:
    loop.run_forever()
except:
    pass
finally:
    for runner in runners:
        loop.run_until_complete(runner.cleanup())
