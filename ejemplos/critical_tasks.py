import asyncio
import spade
from PriorityAsyncio.base_events import PrioritizedEventLoop
import PriorityAsyncio.tasks 
import PriorityAsyncio.locks
import time

# Contador global para puntuación
global_score = 0
critical_tasks = 0

# Tiempo global para controlar la duración del experimento
start_time = None
experiment_duration = 5  # Duración en segundos

# Lock para sincronizar actualizaciones del contador global
score_lock = asyncio.Lock()
start_event = PriorityAsyncio.locks.PrioritizedEvent(priority=-20)  # Event to signal agents to start sending messages

class TaskAgent(spade.agent.Agent):
    class CriticalTaskBehaviour(spade.behaviour.PeriodicBehaviour):
        async def run(self):
            await start_event.wait()  # Wait until the experiment starts
            global global_score, critical_tasks, start_time
            if time.time() - start_time > experiment_duration:
                start_event.clear()  # Detener ejecución si se excede el tiempo
            async with score_lock:
                global_score += 10
                critical_tasks += 1
            #print(f"[CRITICAL] {self.agent.name} ejecutó tarea crítica. +10 puntos")

    class RoutineTaskBehaviour(spade.behaviour.PeriodicBehaviour):
        async def run(self):
            await start_event.wait()  # Wait until the experiment starts
            global global_score, start_time
            if time.time() - start_time > experiment_duration:
                start_event.clear()  # Detener ejecución si se excede el tiempo
            async with score_lock:
                global_score += 2
            #print(f"[ROUTINE] {self.agent.name} ejecutó tarea rutinaria. +2 puntos")

    class MaintenanceTaskBehaviour(spade.behaviour.PeriodicBehaviour):
        async def run(self):
            await start_event.wait()  # Wait until the experiment starts
            global global_score, start_time
            if time.time() - start_time > experiment_duration:
                start_event.clear()  # Detener ejecución si se excede el tiempo
            async with score_lock:
                global_score += 5
            #print(f"[MAINTENANCE] {self.agent.name} ejecutó tarea de mantenimiento. +5 puntos")

    async def setup(self):
        # Alta prioridad para tareas críticas
        critical_behaviour = self.CriticalTaskBehaviour(period=0.01, priority=-3)
        self.add_behaviour(critical_behaviour)

        # Prioridad media para tareas de mantenimiento
        maintenance_behaviour = self.MaintenanceTaskBehaviour(period=0.01, priority=-2)
        self.add_behaviour(maintenance_behaviour)

        # Baja prioridad para tareas rutinarias
        routine_behaviour = self.RoutineTaskBehaviour(period=0.01, priority=-1)
        self.add_behaviour(routine_behaviour)

async def main():

    list_scores = []
    list_critical_tasks = []
    num_experiments = 3

    for j in range (0,num_experiments): 
        print(j)
        global global_score, critical_tasks, start_time
        global_score = 0
        critical_tasks = 0
        agents = []
        num_agents = 20

        # Crear y lanzar agentes
        for i in range(1, num_agents + 1):
            agent = TaskAgent(f"agent_{i}@gtirouter.dsic.upv.es", "test")
            await agent.start()
            agents.append(agent)

        start_time = time.time()

        # Ejecutar el experimento durante un tiempo determinado
        print("Ejecutando experimento con prioridades...")
        start_event.set()
        await PriorityAsyncio.tasks.sleep(experiment_duration, priority=-20)  # Run experiment for 5 seconds
        start_event.clear()

        # Detener agentes
        for agent in agents:
            await agent.stop()

            #loop = asyncio.get_event_loop()
            #task = loop.create_task(agent.stop(), priority = -20)
            #await task

        # Imprimir puntuación final
        #print(f"Puntuación final con prioridades: {global_score}")
        list_scores.append(global_score)
        #print(f"Número de tareas críticas completadas: {critical_tasks}")
        list_critical_tasks.append(critical_tasks)

    print(list_scores)
    print(list_critical_tasks)
    print("Average Total Scores: {:.2f}".format(sum(list_scores)/num_experiments))
    print("Average Critical Tasks Completed : {:.2f}".format(sum(list_critical_tasks)/num_experiments))
    
if __name__ == "__main__":
    # Usar el bucle de eventos con prioridad
    
    spade.run(main())
