import asyncio
import spade
import sys
from PriorityAsyncio.base_events import PrioritizedEventLoop
import PriorityAsyncio.tasks 
import PriorityAsyncio.locks


total_messages_sent = 0 
start_event = PriorityAsyncio.locks.PrioritizedEvent(priority=-3) 

class SenderAgent(spade.agent.Agent):
    class SendMsgBehaviour(spade.behaviour.PeriodicBehaviour):
        async def run(self):
            global total_messages_sent
            await start_event.wait()  
            # gtirouter.dsic.upv.es // localhost
            msg = spade.message.Message(to="agent_100@localhost", body="Hello", metadata={"performative": "inform"})
            #await self.send(msg)
            
            loop = asyncio.get_event_loop()
            task = loop.create_task(self.send(msg), ag_name = f"{self.agent.ag_name}_send$")
            await task

            total_messages_sent += 1

    async def setup(self):
        send_behaviour = self.SendMsgBehaviour(period=0.005)
        self.add_behaviour(send_behaviour)

class ReceiverAgent(spade.agent.Agent):
    reply_count = 0

    class ReceiveMsgBehaviour(spade.behaviour.CyclicBehaviour):
        async def run(self):

            loop = asyncio.get_event_loop()
            task = loop.create_task(self.receive(timeout = 1), ag_name = f"{self.agent.ag_name}_receive$")
            msg = await task


            if msg:
                sender_jid = str(msg.sender)
                reply = spade.message.Message(to=sender_jid, body="Reply", metadata={"performative": "inform"})

                task = loop.create_task(self.send(reply), ag_name = f"{self.agent.ag_name}_reply$")
                await task

                ReceiverAgent.reply_count += 1

                               

    async def setup(self):
        recv_behaviour = self.ReceiveMsgBehaviour()
        self.add_behaviour(recv_behaviour)

async def main():

    list_messages_sent = []
    list_messages_reply = []
    list_reply_percentages = []
    num_experiments = 1

    for j in range (0,num_experiments): 
        print(j)
        global total_messages_sent
        total_messages_sent = 0
        ReceiverAgent.reply_count = 0

        receiver_agent = ReceiverAgent("agent_100@localhost", "test", priority = 0, ag_name="Agent_R")
        await receiver_agent.start()

        sender_agents = [SenderAgent(f"agent_{i}@localhost", "test", priority = 0, ag_name= f"Agent_S{i}") for i in range(1, 21)]
        for agent in sender_agents:
            await agent.start()

        start_event.set()

        print("Comienza el sleep")
        await PriorityAsyncio.tasks.sleep(5, priority=-3) 

        start_event.clear()
        
        for agent in sender_agents:
            await agent.stop()
        await receiver_agent.stop()


        reply_percentage = (ReceiverAgent.reply_count / total_messages_sent) * 100 if total_messages_sent > 0 else 0
        #print(f"Total Messages Sent: {total_messages_sent}")
        list_messages_sent.append(total_messages_sent)
        #print(f"Messages Replied by Agent 100: {ReceiverAgent.reply_count}")
        list_messages_reply.append(ReceiverAgent.reply_count)
        #print(f"Reply Percentage: {reply_percentage:.2f}%")
        list_reply_percentages.append(reply_percentage)
    

    print(list_messages_sent)
    print(list_messages_reply)
    print(list_reply_percentages)
    print(f"Average Total Messages Sent: {(sum(list_messages_sent)/num_experiments)}")
    print(f"Average Messages Replied : {(sum(list_messages_reply)/num_experiments)}")
    print(f"Average Reply Percentage: {(sum(list_reply_percentages)/num_experiments):.2f}%")




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