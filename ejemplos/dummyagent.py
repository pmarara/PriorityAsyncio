import asyncio
import datetime
import spade
import sys
from PriorityAsyncio.base_events import PrioritizedEventLoop

class SimpleSenderAgent(spade.agent.Agent):

    class SendBehaviour(spade.behaviour.CyclicBehaviour):
        async def run(self):
            print(f"Hola Mundo")
            
            self.counter +=1
            if self.counter == 5:
                self.kill()
                self.agent.finished = True

    async def setup(self):
        b = self.SendBehaviour(priority=1)
        b.counter = 0
        c = self.SendBehaviour(priority=2)  
        c.counter = 0
        self.add_behaviour(c)
        self.add_behaviour(b)


async def main():

    sender_agent = SimpleSenderAgent("agent_sender@gtirouter.dsic.upv.es", "test", ag_name = "Agente1")
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

    # OPCIÓN 1
    #loop = PrioritizedEventLoop()
    #asyncio.set_event_loop(loop)
    #asyncio.run(main()) #NO EJECUTA PrioritizedEventLoop!!

    # OPCIÓN 2
    spade.run(main())

    # OPCIÓN 3
    #loop = PrioritizedEventLoop()
    #loop.run_until_complete(main())

    