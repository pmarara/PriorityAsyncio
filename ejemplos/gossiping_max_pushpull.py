import datetime
import json
import random
import time
import asyncio
import spade
import sys
from PriorityAsyncio.base_events import PrioritizedEventLoop
import PriorityAsyncio.tasks 
import PriorityAsyncio.locks


class PushPullAgent(spade.agent.Agent):

    async def setup(self):
        self.value = random.randint(1, 1000)
        self.messages_sent = 0  # Contador de mensajes enviados por el agente
        self.priority =  0 - self.value # Prioridad asignada al primer comportamiento
        start_at = datetime.datetime.now() + datetime.timedelta(seconds=5)
        pp = self.PushPullBehaviour(period=2, start_at=start_at , priority = self.priority)
        # Usar para mostrar en Kiwi pp.name = "Push$"
        self.add_behaviour(pp) 
        template = spade.template.Template(metadata={"performative": "PUSHPULL"})
        r = self.RecvBehaviour(priority = 0)
        # Usar para mostrar en Kiwi r.name = "Pull$"
        self.add_behaviour(r, template)
        template = spade.template.Template(metadata={"performative": "REPLY"})
        r2 = self.Recv2Behaviour(priority = 0)
        # Usar para mostrar en Kiwi r2.name = "Reply$"
        self.add_behaviour(r2, template)

        print("{} ready.".format(self.name))

    def add_value(self, value):
        # Actualización al valor más alto
        self.value = max(self.value, value)

    def add_contacts(self, contact_list):
        self.contacts = [c.jid for c in contact_list if c.jid != self.jid]
        self.length = len(self.contacts)

    # Comportamiento encargado de enviar el mensaje pushpull
    class PushPullBehaviour(spade.behaviour.PeriodicBehaviour):

        async def run(self):
            k = 2 
            random_contacts = random.sample(self.agent.contacts, k)

            # Enviar solicitud PUSHPULL a los contactos seleccionados
            for jid in random_contacts:
                body = json.dumps({"value": self.agent.value, "timestamp": time.time(), "request": "PUSHPULL"})
                msg = spade.message.Message(to=str(jid), body=body, metadata={"performative": "PUSHPULL"})
                await self.send(msg)
                self.agent.messages_sent += 1  # Incrementar el contador de mensajes enviados

            await asyncio.sleep(0)

                   
    # Comportamiento encargado de gestionar la llegada de un mensaje pushpull
    class RecvBehaviour(spade.behaviour.CyclicBehaviour):
        async def run(self):
            
            msg = await self.receive(timeout=2)
            if msg:
                response = json.loads(msg.body)
                # Llamamos al método encargado de decidir si actualiza el dato o no
                self.agent.add_value(response["value"])
                body = json.dumps({"value": self.agent.value, "timestamp": time.time()})
                msg = spade.message.Message(to=str(msg.sender), body=body, metadata={"performative": "REPLY"})
                await self.send(msg)

    # comportamiento encargado de gestionar la llegada de un mensaje reply
    class Recv2Behaviour(spade.behaviour.CyclicBehaviour):
        async def run(self):
            
            msg = await self.receive(timeout=2)
            if msg:
                body = json.loads(msg.body)
                # llamamos al método encargado de decidir si actualiza el dato o no
                self.agent.add_value(body["value"])

async def main():


    num_experiments = 10
    count=50

    list_elapsed_time = []
    list_total_messages = []
    list_messages_second = []
    list_average_messages_per_agent = []

    for j in range (0,num_experiments): 
        print(j)
        agents = []
        start_time = time.time()

        print("Creating {} agents...".format(count))
        for x in range(1, count+1):
            print("Creating agent {}...".format(x))
            # Nos guardamos la lista de agentes para poder visualizar el estado del proceso gossiping
            # El servidor está fijado a gtirouter.dsic.upv.es, si se tiene un servidor XMPP en local, se puede sustituir por localhost
            a = PushPullAgent("agent_{}@localhost".format(x), "test", ag_name = "Agent_{}".format(x))
            agents.append(a)

        # este tiempo trata de esperar que todos los agentes estan registrados, depende de la cantidad de agentes que se lancen
        await asyncio.sleep(3)

        # se le pasa a cada agente la lista de contactos
        for ag in agents:
            ag.add_contacts(agents)
            ag.value = 0

        # se lanzan todos los agentes
        for ag in agents:

            await ag.start()

            # Posible lanzamiento de los agentes
            #loop = asyncio.get_event_loop()
            #task = loop.create_task(ag.start(), priority = -1001)
            #await task


        # este tiempo trata de esperar que todos los agentes estan ready, depende de la cantidad de agentes que se lancen
        await asyncio.sleep(1)


        # Este bucle imprime los valores que almacena cada agente y termina cuando todos tienen el mismo valor (consenso)
        while True:
            try:
                await asyncio.sleep(1)
                status = [ag.value for ag in agents]
                print("STATUS: {}".format(status))
                if len(set(status)) <= 1:
                    print("Gossip done.")
                    elapsed_time = time.time() - start_time
                    break
            except KeyboardInterrupt:
                break

        # se paran todos los agentes
        for ag in agents:
            await ag.stop()
        print("Agents finished")

        # Imprimir resultados
        total_messages_sent = sum(ag.messages_sent for ag in agents)
        #print("Elapsed Time: {:.2f} seconds".format(elapsed_time))
        list_elapsed_time.append(elapsed_time)
        #print("Total Messages Sent: {}".format(total_messages_sent))
        list_total_messages.append(total_messages_sent)
        #print("Messages/Second: {:.2f}".format(total_messages_sent/elapsed_time))
        list_messages_second.append(total_messages_sent/elapsed_time)
        #print("Average Messages Sent per Agent: {:.2f}".format(total_messages_sent / count))
        list_average_messages_per_agent.append(total_messages_sent / count)

    print(list_elapsed_time)
    print(list_total_messages)
    print(list_messages_second)
    print(list_average_messages_per_agent)
    print("Average Elapsed Time: {:.2f} seconds".format((sum(list_elapsed_time)/num_experiments)))   
    print("AverageTotal Messages Sent: {}".format((sum(list_total_messages)/num_experiments)))
    print("Average Messages/Second: {:.2f}".format((sum(list_messages_second)/num_experiments)))
    print("Average Messages Sent per Agent: {:.2f}".format((sum(list_average_messages_per_agent)/num_experiments)))

if __name__ == "__main__":

        spade.run(main())