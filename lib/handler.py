import sys
import asyncio
import concurrent.futures

from .utils import log, traceback_error
from .exception import TranslationCanceled


class Handler:
    def __init__(self, paragraphs, concurrency_limit, translate_paragraph,
                 process_translation, request_interval):
        self.queue = asyncio.Queue()
        # Bounded done-queue: if the consumer (GUI/editor) is slower than the
        # translation workers, workers block on put() instead of growing the
        # queue without limit.
        self.done_queue = asyncio.Queue(maxsize=64)
        self.stats = {'done': 0, 'errors': 0}

        for paragraph in paragraphs:
            self.queue.put_nowait(paragraph)

        self.concurrency_limit = concurrency_limit or self.queue.qsize()
        self.translate_paragraph = translate_paragraph
        self.process_translation = process_translation
        self.request_interval = request_interval
        # One shared thread pool for the whole run (the stock version built a
        # new ThreadPoolExecutor per processed paragraph).
        self.pool = None

    def _ensure_pool(self):
        if self.pool is None:
            self.pool = concurrent.futures.ThreadPoolExecutor(
                max_workers=self.concurrency_limit + 2,
                thread_name_prefix='better-translator')
        return self.pool

    async def translation_worker(self):
        loop = asyncio.get_running_loop()
        pool = self._ensure_pool()
        while True:
            paragraph = await self.queue.get()
            try:
                await loop.run_in_executor(
                    pool, self.translate_paragraph, paragraph)
                paragraph.error = None
                if self.queue.qsize() > 0 and not paragraph.is_cache:
                    await asyncio.sleep(self.request_interval)
                await self.done_queue.put(paragraph)
                self.stats['done'] += 1
                self.queue.task_done()
            except TranslationCanceled:
                await self.cancel_tasks()
                break
            except Exception:
                paragraph.error = traceback_error()
                self.stats['errors'] += 1
                await self.done_queue.put(paragraph)
                self.queue.task_done()

    async def processing_worker(self):
        loop = asyncio.get_running_loop()
        pool = self._ensure_pool()
        while True:
            paragraph = await self.done_queue.get()
            await loop.run_in_executor(pool, self.process_translation, paragraph)
            self.done_queue.task_done()

    async def cancel_tasks(self):
        self.queue.task_done()
        while not self.queue.empty():
            await self.queue.get()
            self.queue.task_done()
        while not self.done_queue.empty():
            done = await self.done_queue.get()
            self.done_queue.task_done()

    async def create_tasks(self):
        tasks = []
        for _ in range(self.concurrency_limit):
            tasks.append(asyncio.create_task(self.translation_worker()))
        tasks.append(asyncio.create_task(self.processing_worker()))
        return tasks

    async def process_tasks(self):
        tasks = await self.create_tasks()
        await self.queue.join()
        await self.done_queue.join()
        # Terminate infinitive loop worker.
        for task in tasks:
            task.cancel()
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        if self.pool is not None:
            self.pool.shutdown(wait=False)

    def handle(self):
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(
                asyncio.WindowsProactorEventLoopPolicy())
        try:
            loop = asyncio.get_event_loop()
        except Exception:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(self.process_tasks())
