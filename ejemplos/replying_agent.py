import asyncio
import spade
import sys
sys.path.append("..")
from base_events import PrioritizedEventLoop


# If using uvloop, uncomment these lines
#import uvloop
#asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

total_messages_sent = 0  # Global variable to track total messages sent

class SenderAgent(spade.agent.Agent):
    class SendMsgBehaviour(spade.behaviour.PeriodicBehaviour):
        async def run(self):
            global total_messages_sent
            # gtirouter.dsic.upv.es
            msg = spade.message.Message(to="agent_100@gtirouter.dsic.upv.es", body="Hello", metadata={"performative": "inform"})
            await self.send(msg)
            total_messages_sent += 1

    async def setup(self):
        send_behaviour = self.SendMsgBehaviour(period=0.01)
        self.add_behaviour(send_behaviour)

class ReceiverAgent(spade.agent.Agent):
    reply_count = 0

    class ReceiveMsgBehaviour(spade.behaviour.CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=1)  # Adjust timeout as needed
            if msg:
                sender_jid = str(msg.sender)
                reply = spade.message.Message(to=sender_jid, body="Reply", metadata={"performative": "inform"})
                await self.send(reply)
                ReceiverAgent.reply_count += 1
                
                

    async def setup(self):
        recv_behaviour = self.ReceiveMsgBehaviour()
        self.add_behaviour(recv_behaviour)

async def main():
    global total_messages_sent
    receiver_agent = ReceiverAgent("agent_100@gtirouter.dsic.upv.es", "test")
    await receiver_agent.start()

    sender_agents = [SenderAgent(f"agent_{i}@gtirouter.dsic.upv.es", "test") for i in range(1, 21)]
    for agent in sender_agents:
        await agent.start()

    await asyncio.sleep(5)  # Run experiment for 5 seconds

    for agent in sender_agents:
        await agent.stop()
    await receiver_agent.stop()

    reply_percentage = (ReceiverAgent.reply_count / total_messages_sent) * 100 if total_messages_sent > 0 else 0
    print(f"Total Messages Sent: {total_messages_sent}")
    print(f"Messages Replied by Agent 100: {ReceiverAgent.reply_count}")
    print(f"Reply Percentage: {reply_percentage:.2f}%")

# Adjusted execution pattern for environments with an already running event loop
if __name__ == "__main__":

    loop = PrioritizedEventLoop()
    #loop = asyncio.events.get_event_loop()

    asyncio.set_event_loop(loop)  

    if loop.is_running():
        loop.create_task(main())
    else:
        loop.run_until_complete(main())