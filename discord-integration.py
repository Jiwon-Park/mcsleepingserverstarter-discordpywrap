import subprocess
from decouple import config
import discord
import asyncio
from prompt_toolkit import prompt, PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from multiprocessing import Process
from threading import Thread
import signal
import traceback

GUILD_ID = int(config('GUILD_ID'))
CHANNEL_ID = int(config('CHANNEL_ID'))
TOKEN = config('TOKEN')

client = discord.Client(intents=discord.Intents.default())

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

async def send_message(msg):
    guild = client.get_guild(GUILD_ID)
    channel = guild.get_channel(CHANNEL_ID)
    await channel.send(msg)

async def control(process: asyncio.subprocess.Process, CtoI: asyncio.Queue, ItoC: asyncio.Queue):
    print("서버가 시작되었습니다.")
    
    async def readfunc(loop) -> bytes:
        while True:
            try:
                coro = process.stdout.readline()
                future = asyncio.ensure_future(coro)

                yield await asyncio.wait_for(future, 1)
            except asyncio.TimeoutError:
                await asyncio.sleep(1)
                yield b'timeout\n'
            except Exception as e:
                print("Exception in readfunc")
                print(*traceback.format_exception(None, e, e.__traceback__), sep='\n')
                
                await asyncio.sleep(1)
                yield b'Exception\n'
                break
    try:
        loop = asyncio.get_running_loop()
        async for c in readfunc(loop):
            line = c.decode('utf-8').strip()
            if line != 'timeout':
                print(line)
            if len(line) > 70 and line.endswith('joined the game'):
                name = line[61:-16]
                print(name, "님이 서버에 접속하셨습니다.")
                client.loop.create_task(send_message(f'{name} 님이 서버에 접속하셨습니다.'))
            elif len(line) > 70 and line.endswith('left the game'):
                name = line[61:-14]
                print(name, "님이 서버에서 나가셨습니다.")
                client.loop.create_task(send_message(f'{name} 님이 서버에서 나가셨습니다.'))
            elif len(line) > 70 and line.endswith(' seconds to load'):
                print("서버가 절전 모드에서 켜졌습니다.")
                client.loop.create_task(send_message("서버가 절전 모드에서 켜졌습니다."))
            elif line.endswith('Ready for battle'):
                print("서버가 절전 모드로 들어갔습니다.")
                client.loop.create_task(send_message("서버가 절전 모드로 들어갔습니다. 켜려면 craft.seni.kr:25566에 접속하세요"))
            
            if not ItoC.empty():
                inp = await ItoC.get()
                if inp == "exit\n":
                    print("서버 끄는 중...")
                    try:
                        process.send_signal(signal.CTRL_C_EVENT)
                    except Exception as e:
                        pass
                    await asyncio.sleep(20)
                    # process.kill()
                else:
                    process.stdin.write(inp.encode('utf-8'))
                    await process.stdin.drain()
    except Exception as e:
        print("Exception in Control")
        print(*traceback.format_exception(None, e, e.__traceback__), sep='\n')
    finally:
        print("Control 종료됨")
        CtoI.put_nowait("exit\n")
        try:
            process.terminate()
        except Exception as e:
            pass
        return 0

async def inputProcess(process: asyncio.subprocess.Process, CtoI: asyncio.Queue, ItoC: asyncio.Queue):
    session = PromptSession()
    try:
        with patch_stdout():
            while True:
                if not CtoI.empty():
                    if await CtoI.get() == "exit\n":
                        break
                inp = await session.prompt_async(">> ") + '\n'
                print(inp)
                if inp == "exit\n":
                    print("exitting...")
                    await ItoC.put("exit\n")
                    # process.kill()
                else:
                    await ItoC.put(inp)

    except Exception as e:
        print("Exception in Input")
        print(*traceback.format_exception(None, e, e.__traceback__), sep='\n')
    finally:
        print("Input 종료됨")
        return 0

async def runserver():
    q1 = asyncio.Queue()
    q2 = asyncio.Queue()
    process = await asyncio.subprocess.create_subprocess_exec("mcsleepingserverstarter-win-x64.exe", stdout=asyncio.subprocess.PIPE, stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    loop2 = asyncio.new_event_loop()
    th2 = Thread(target=loop2.run_until_complete, args=(inputProcess(process, q1, q2),))
    th2.start()

    await control(process, q1, q2)

    # th1.start()
    th2.join()
    loop2.close()
    # th1.join()
    return 0


async def main():
    loop = asyncio.get_running_loop()
    task = asyncio.tasks.create_task(client.start(TOKEN))

    _ = await runserver()

    print("서버 스레드가 종료되었습니다.")
    task2 = asyncio.tasks.create_task(client.close())
    while not task2.done():
        await asyncio.sleep(1)
    while not task.done():
        await asyncio.sleep(1)
    print("디스코드 스레드가 종료되었습니다.")

asyncio.run(main(), debug=True)