import asyncio
import datetime
import spade
import sys
sys.path.append("..")
from base_events import PrioritizedEventLoop

class SimpleSenderAgent(spade.agent.Agent):
    class SendBehaviour(spade.behaviour.PeriodicBehaviour):
        async def run(self):
            msg = spade.message.Message(to="agent_receiver@gtirouter.dsic.upv.es", body="Hello World", metadata={"performative": "inform"})
            await self.send(msg)
            print(f"Message sent at {datetime.datetime.now()}")
            self.kill()

    async def setup(self):
        b = self.SendBehaviour(period=0.5)
        self.add_behaviour(b)

class SimpleReceiverAgent(spade.agent.Agent):
    class ReceiveBehaviour(spade.behaviour.CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                print(f"Received message at {datetime.datetime.now()}: {msg.body}")
                self.kill()

    async def setup(self):
        b = self.ReceiveBehaviour()
        self.add_behaviour(b)

async def main():
    receiver_agent = SimpleReceiverAgent("agent_receiver@gtirouter.dsic.upv.es", "test")
    await receiver_agent.start()
    print("Receiver agent started")

    sender_agent = SimpleSenderAgent("agent_sender@gtirouter.dsic.upv.es", "test")
    await sender_agent.start()
    print("Sender agent started")

    # Wait until agents finish their jobs
    await asyncio.sleep(1)
    await sender_agent.stop()
    await receiver_agent.stop()

if __name__ == "__main__":
    loop = PrioritizedEventLoop()
    asyncio.set_event_loop(loop)
    spade.run(main())
    #loop.run_until_complete(main())