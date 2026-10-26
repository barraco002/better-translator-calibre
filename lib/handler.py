import asyncio
import concurrent.futures

from .utils import log, traceback_error
from .exception import TranslationCanceled


class Handler:
    def __init__(self, paragraphs, concurrency_limit, translate_paragraph,
                 process_translation, request_interval, on_stop=None):
        self.queue = asyncio.Queue()
        # Bounded done-queue: if the consumer (GUI/editor) is slower than the
        # translation workers, workers block on put() instead of growing the
        # queue without limit.
        self.done_queue = asyncio.Queue(maxsize=64)
        self.stats = {'done': 0, 'errors': 0}

        for paragraph in paragraphs:
            self.queue.put_nowait(paragraph)

        # A zero limit means automatic, never one thread per paragraph.
        self.concurrency_limit = max(1, min(
            int(concurrency_limit or 6), max(1, self.queue.qsize())))
        self.translate_paragraph = translate_paragraph
        self.process_translation = process_translation
        self.request_interval = request_interval
        self.on_stop = on_stop
        # One shared thread pool for the whole run (the stock version built a
        # new ThreadPoolExecutor per processed paragraph).
        self.pool = None

    def _ensure_pool(self):
        if self.pool is None:
            self.pool = concurrent.futures.ThreadPoolExecutor(
                max_workers=self.concurrency_limit + 1,
                thread_name_prefix='better-translator')
        return self.pool

    async def translation_worker(self):
        loop = asyncio.get_running_loop()
        pool = self._ensure_pool()
        while True:
            paragraph = await self.queue.get()
            try:
                try:
                    await loop.run_in_executor(
                        pool, self.translate_paragraph, paragraph)
                    paragraph.error = None
                    self.stats['done'] += 1
                except TranslationCanceled:
                    raise
                except Exception:
                    paragraph.error = traceback_error()
                    self.stats['errors'] += 1
                await self.done_queue.put(paragraph)
                if self.queue.qsize() > 0 and not paragraph.is_cache:
                    await asyncio.sleep(max(0, self.request_interval))
            finally:
                self.queue.task_done()

    async def processing_worker(self):
        loop = asyncio.get_running_loop()
        pool = self._ensure_pool()
        while True:
            paragraph = await self.done_queue.get()
            try:
                await loop.run_in_executor(
                    pool, self.process_translation, paragraph)
            finally:
                self.done_queue.task_done()

    async def create_tasks(self):
        tasks = []
        for _ in range(self.concurrency_limit):
            tasks.append(asyncio.create_task(self.translation_worker()))
        tasks.append(asyncio.create_task(self.processing_worker()))
        return tasks

    async def process_tasks(self):
        tasks = await self.create_tasks()

        async def drained():
            await self.queue.join()
            await self.done_queue.join()

        completion = asyncio.create_task(drained())
        try:
            done, _ = await asyncio.wait(
                tasks + [completion], return_when=asyncio.FIRST_COMPLETED)
            # Surface worker/callback failures even if the queues just drained.
            for task in tasks:
                if task in done:
                    task.result()
            if completion in done:
                completion.result()
        finally:
            if self.on_stop is not None:
                self.on_stop()
            for task in tasks + [completion]:
                task.cancel()
            await asyncio.gather(*tasks, completion, return_exceptions=True)
            if self.pool is not None:
                # Running requests finish under their configured timeout. No
                # callbacks may outlive the event loop or touch a closed cache.
                self.pool.shutdown(wait=True)

    def handle(self):
        asyncio.run(self.process_tasks())
