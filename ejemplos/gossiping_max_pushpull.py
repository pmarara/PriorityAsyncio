import datetime
import json
import random
import time
import asyncio
import spade
import sys
sys.path.append("..")
from base_events import PrioritizedEventLoop

# If using uvloop, uncomment these lines
#import uvloop
#asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class PushPullAgent(spade.agent.Agent):

    async def setup(self):
        self.value = random.randint(1, 1000)
        self.messages_sent = 0  # Contador de mensajes enviados por el agente

        start_at = datetime.datetime.now() + datetime.timedelta(seconds=5)
        self.add_behaviour(self.PushPullBehaviour(period=2, start_at=start_at))
        template = spade.template.Template(metadata={"performative": "PUSHPULL"})
        self.add_behaviour(self.RecvBehaviour(), template)
        template = spade.template.Template(metadata={"performative": "REPLY"})
        self.add_behaviour(self.Recv2Behaviour(), template)

        print("{} ready.".format(self.name))

    def add_value(self, value):
        # Actualización del valor al promedio
        self.value = max(self.value, value)

    def add_contacts(self, contact_list):
        self.contacts = [c.jid for c in contact_list if c.jid != self.jid]
        self.length = len(self.contacts)

    # Comportamiento encargado de enviar el mensaje pushpull
    class PushPullBehaviour(spade.behaviour.PeriodicBehaviour):

        async def run(self):
            k = 5 # El número de amigos está fijado a 1, se puede modificar
            random_contacts = random.sample(self.agent.contacts, k)

            # Enviar solicitud PUSHPULL a los amigos seleccionados
            for jid in random_contacts:
                body = json.dumps({"value": self.agent.value, "timestamp": time.time(), "request": "PUSHPULL"})
                msg = spade.message.Message(to=str(jid), body=body, metadata={"performative": "PUSHPULL"})
                await self.send(msg)
                self.agent.messages_sent += 1  # Incrementar el contador de mensajes enviados

                   
            

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
    count=50
    agents = []
    start_time = time.time()

    print("Creating {} agents...".format(count))
    for x in range(1, count + 1):
        print("Creating agent {}...".format(x))
        # nos guardamos la lista de agentes para poder visualizar el estado del proceso gossiping
        # el servidor está fijado a gtirouter.dsic.upv.es, si se tiene un serviodor XMPP en local, se puede sustituir por localhost
        agents.append(PushPullAgent("agent_{}@gtirouter.dsic.upv.es".format(x), "test"))

    # este tiempo trata de esperar que todos los agentes estan registrados, depende de la cantidad de agentes que se lancen
    await asyncio.sleep(3)

    # se le pasa a cada agente la lista de contactos
    for ag in agents:
        ag.add_contacts(agents)
        ag.value = 0

    # se lanzan todos los agentes
    for ag in agents:
        await ag.start()

    # este tiempo trata de esperar que todos los agentes estan ready, depende de la cantidad de agentes que se lancen
    await asyncio.sleep(1)

    # este bucle imprime los valores que almacena cada agente y termina cuando todos tienen el mismo valor (consenso)
    while True:
        try:
            await asyncio.sleep(1)
            status = [ag.value for ag in agents]
            print("STATUS: {}".format(status))
            if len(set(status)) <= 1:
                print("Gossip done.")
                break
        except KeyboardInterrupt:
            break

    # se para a todos los agentes
    for ag in agents:
        await ag.stop()
    print("Agents finished")

    # Imprimir resultados
    elapsed_time = time.time() - start_time
    total_messages_sent = sum(ag.messages_sent for ag in agents)
    print("Elapsed Time: {:.2f} seconds".format(elapsed_time))
    print("Total Messages Sent: {}".format(total_messages_sent))
    print("Messages/Second: {:.2f}".format(total_messages_sent/elapsed_time))
    print("Average Messages Sent per Agent: {:.2f}".format(total_messages_sent / count))
    print("Agents finished")

if __name__ == "__main__":

    loop = PrioritizedEventLoop()
    #loop = asyncio.events.get_event_loop()

    asyncio.set_event_loop(loop)  

    if loop.is_running():
        loop.create_task(main())
    else:
        spade.run(main())