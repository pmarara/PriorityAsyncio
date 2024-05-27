import asyncio
import sys
sys.path.append("..")
import base_events, tasks, locks
import random



loop = base_events.PrioritizedEventLoop()
asyncio.set_event_loop(loop)  

# Usage
async def example_task(priority, name, event):
    print(f'Task {name} started with priority {priority}')
    await event.wait() # Introduce a delay for each task
    print(f'Task {name} finished with priority {priority} ')





async def main(loop):

    event = asyncio.Event()

    task_names = list(chr(i) for i in range(65, 75))  # Generate task names (A-J)

    # Use random.sample to get 10 unique priorities from 1 to 10
    priorities = random.sample(range(1, 11), 10)
    print(priorities)

    for i, name in enumerate(task_names):

        #loop.create_task(tasks.PrioritizedTask(example_task(priorities[i], name, event), priority = priorities[i]))

        loop.create_task(example_task(priorities[i], name, event), priority = priorities[i])

    
    await asyncio.sleep(2)


    event.set()


# Uncomment if using custom loop policy (optional)
# asyncio.set_event_loop_policy(PrioritizedEventLoopPolicy())

loop.run_until_complete(main(loop))




