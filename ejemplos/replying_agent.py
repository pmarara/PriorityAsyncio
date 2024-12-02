import asyncio
import spade
import sys
from PriorityAsyncio.base_events import PrioritizedEventLoop
import PriorityAsyncio.tasks 
import PriorityAsyncio.locks


# If using uvloop, uncomment these lines
#import uvloop
#asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

total_messages_sent = 0  # Global variable to track total messages sent
start_event = PriorityAsyncio.locks.PrioritizedEvent(priority=-2)  # Event to signal agents to start sending messages

class SenderAgent(spade.agent.Agent):
    class SendMsgBehaviour(spade.behaviour.PeriodicBehaviour):
        async def run(self):
            global total_messages_sent
            await start_event.wait()  # Wait until the experiment starts
            # gtirouter.dsic.upv.es
            #print("Envío de mensaje")
            msg = spade.message.Message(to="agent_100@gtirouter.dsic.upv.es", body="Hello", metadata={"performative": "inform"})
            #await self.send(msg)
            
            loop = asyncio.get_event_loop()
            task = loop.create_task(self.send(msg), ag_name = f"{self.agent.ag_name}_send$")
            await task

            total_messages_sent += 1

    async def setup(self):
        send_behaviour = self.SendMsgBehaviour(period=0.005, priority = 0)
        self.add_behaviour(send_behaviour)

class ReceiverAgent(spade.agent.Agent):
    reply_count = 0

    class ReceiveMsgBehaviour(spade.behaviour.CyclicBehaviour):
        async def run(self):
            #msg = await self.receive(timeout = 1)  # Adjust timeout as needed

            loop = asyncio.get_event_loop()
            task = loop.create_task(self.receive(timeout = 1), ag_name = f"{self.agent.ag_name}_receive$")
            msg = await task

            #print("Recibo de mensaje")
            if msg:
                sender_jid = str(msg.sender)
                reply = spade.message.Message(to=sender_jid, body="Reply", metadata={"performative": "inform"})

                #await self.send(reply)
                task = loop.create_task(self.send(reply), ag_name = f"{self.agent.ag_name}_reply$")
                await task

                ReceiverAgent.reply_count += 1
                #await asyncio.sleep(1)
                #task = loop.create_task(asyncio.sleep(1), ag_name = f"{self.agent.ag_name}_sleep$")
                #await task
                
                

    async def setup(self):
        recv_behaviour = self.ReceiveMsgBehaviour(priority = -1)
        self.add_behaviour(recv_behaviour)

async def main():
    global total_messages_sent
    receiver_agent = ReceiverAgent("agent_100@gtirouter.dsic.upv.es", "test", ag_name="RAgent")
    await receiver_agent.start()

    sender_agents = [SenderAgent(f"agent_{i}@gtirouter.dsic.upv.es", "test", ag_name= f"SAgent{i}") for i in range(1, 21)]
    for agent in sender_agents:
        await agent.start()

    start_event.set()

    print("Comienza el sleep")
    await PriorityAsyncio.tasks.sleep(5, priority=-2)  # Run experiment for 5 seconds

    start_event.clear()
    
    for agent in sender_agents:
        await agent.stop()
    await receiver_agent.stop()


    reply_percentage = (ReceiverAgent.reply_count / total_messages_sent) * 100 if total_messages_sent > 0 else 0
    print(f"Total Messages Sent: {total_messages_sent}")
    print(f"Messages Replied by Agent 100: {ReceiverAgent.reply_count}")
    print(f"Reply Percentage: {reply_percentage:.2f}%")

    loop = asyncio.get_event_loop()

    #print(loop.counterzero)
    #print(loop.counterother)

# Adjusted execution pattern for environments with an already running event loop
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