import asyncio
import datetime
import spade
import sys
sys.path.append("..")
from base_events import PrioritizedEventLoop

class SimpleSenderAgent(spade.agent.Agent):
    class SendBehaviour(spade.behaviour.OneShotBehaviour):
        async def run(self):
            print(f"Hola Mundo")
            #self.kill()
            self.agent.finished = True

    async def setup(self):
        b = self.SendBehaviour()
        self.add_behaviour(b)

async def main():

    sender_agent = SimpleSenderAgent("agent_sender@gtirouter.dsic.upv.es", "test")
    sender_agent.finished = False
    await sender_agent.start()
    print("Sender agent started")

    # Wait until agents finish their jobs
    while not sender_agent.finished:
        await asyncio.sleep(1)
        #print(".", end = "")
    print("While finalizado")
    await sender_agent.stop()

if __name__ == "__main__":
    loop = PrioritizedEventLoop()
    asyncio.set_event_loop(loop)
    spade.run(main())
    #loop.run_until_complete(main())