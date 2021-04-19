import datetime
import time
import csv
import string
import uuid
import random
from functools import partial
from multiprocessing import Pool

import peewee
import psycopg2
from aiorun import run
import asyncio
import logging

from statistics import mean
from aiomisc import ThreadPoolExecutor
from peewee import Proxy
from peewee_asyncext import PooledPostgresqlExtDatabase


from db import db_proxy, ExtendedDBManager, Article
from decorators import async_retry
from settings import Config
from utils import FileReader

logger = logging.getLogger(__name__)


def init_db(conf: Config) -> Proxy:
    db_conf = PooledPostgresqlExtDatabase(
        conf.db_name,
        user=conf.db_user,
        host=conf.db_host,
        port=conf.db_port,
        password=conf.db_pass,
        register_hstore=False,
        autorollback=True,
        min_connections=20,
        max_connections=100
    )

    db_proxy.initialize(db_conf)
    return db_proxy


# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# = = = = = = = = = = = = = = = B E G I N   T E S T S = = = = = = = = = = = = = = = = = = = = =
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
body = """
MINNEAPOLIS — For nearly a year, the country’s understanding of George Floyd’s death has come mostly from a gruesome video of a white Minneapolis police officer kneeling on Mr. Floyd’s neck for more than nine minutes. It has become, for many, a painful encapsulation of racism in policing.
But as the murder trial of the officer, Derek Chauvin, opened on Monday, his lawyer attempted to convince jurors that there was more to know about Mr. Floyd’s death than the stark video.
The case was about Mr. Floyd’s drug use, the lawyer, Eric J. Nelson, argued. It was about Mr. Floyd’s size, his resistance of police officers and his weakened heart, the lawyer said. It was about an increasingly agitated crowd that gathered at an intersection in South Minneapolis, which he said diverted Mr. Chauvin’s attention from Mr. Floyd, who was Black. This, Mr. Nelson asserted, was, in part, an overdose, not a police murder.
Prosecutors, however, said that the case was exactly what it seemed to be — and exactly what the video, with its graphic, indelible moments, had revealed.
"""

body = ''


def get_random_string(n=15):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(n))


def _generate_data(index):
    return [
        ('0', f"Title {index} - {i} - {get_random_string(15)}", body, datetime.datetime.now())
        for i in range(1000)
    ]


@async_retry(3, (asyncio.exceptions.TimeoutError, peewee.OperationalError))
async def atom_task(db, data):
    query = Article.insert_many(
        data,
        fields=[Article.status, Article.name, Article.body, Article.created_date]
    )
    await db.execute(query)
    return True


async def reconnect(db):
    if db:
        return await db.connect()


async def start_task(*args, **kwargs):
    return True


async def buck_create_new(db: ExtendedDBManager, epoch_count, mode, count=1000):
    INDEX_INC = 10
    INDEX_COUNTER = 0

    with Pool(10) as p:
        pending = set([asyncio.create_task(start_task())])
        while pending:
            ready, pending = await asyncio.wait(pending, timeout=600, return_when=asyncio.FIRST_COMPLETED)
            logger.info(f"{mode.upper()} Ready = {len(ready)}, pending={len(pending)} INDEX = {INDEX_COUNTER}")

            if (INDEX_COUNTER * 1000) >= count:
                continue

            list_of_data_list = p.map(
                _generate_data, [(epoch_count, i) for i in range(INDEX_COUNTER, INDEX_COUNTER + INDEX_INC)]
            )

            INDEX_COUNTER += INDEX_INC

            pending.update([
                asyncio.create_task(
                    atom_task(db=db, data=data)
                )
                for data in list_of_data_list
            ])

            await asyncio.sleep(0.3)

        logger.info(f"Len pending={len(pending)}")


async def call_avr_time(db: ExtendedDBManager, text, n=20):
    all_tasks = [
        db.execute(Article.raw(sql=f"EXPLAIN ANALYSE SELECT * FROM article where name = '{text}';"))
        for _ in range(n)
    ]
    res = await asyncio.gather(*all_tasks)
    time = [
        float(r[0].replace("Execution Time: ", '').replace(" ms", ''))
        for row in list(res) for r in row._rows
        if r[0].startswith("Execution Time:")]
    avr = mean(time)
    avr_g = 1.3*avr
    avr_l = 0.7*avr
    new_time = [t for t in time if avr_l <= t <= avr_g]
    return mean(new_time) if new_time else avr


async def drop_index(db, index="article_name"):
    try:
        await db.execute(Article.raw(sql=f"DROP INDEX IF EXISTS {index};"))
    except psycopg2.ProgrammingError as e:
        return True
    return False


@async_retry(3, (asyncio.exceptions.TimeoutError, ))
async def create_index(db, index="article_name"):
    try:
        await db.execute(Article.raw(sql=f"CREATE INDEX {index} ON article (name);"))
    except psycopg2.ProgrammingError as e:
        return True
    return False


@async_retry(3, (asyncio.exceptions.TimeoutError, ))
async def vacuum(db):
    try:
        logger.info("Prepare to VACUUM")
        await db.execute(Article.raw(sql="VACUUM(FULL, VERBOSE, ANALYZE) article;"))
        logger.info("VACUUM done!")
    except psycopg2.ProgrammingError as e:
        return True
    return False


@async_retry(3, (asyncio.exceptions.TimeoutError, ))
async def truncate(db):
    try:
        logger.info("TRUNCATE done!")
        await db.execute(Article.raw(sql="TRUNCATE TABLE article;"))
    except psycopg2.ProgrammingError as e:
        return True
    return False


async def main():
    conf = Config()

    logging.basicConfig(level=logging.DEBUG)
    logging.config.dictConfig(conf.DEFAULT_LOGGING)
    logger = logging.getLogger(__name__)

    db = ExtendedDBManager(init_db(conf))
    db.database.create_tables([Article], safe=True)

    executor = ThreadPoolExecutor(max_workers=10)
    loop.set_default_executor(executor)

    DATA_FOR_MATPLOTLIB = {}

    await truncate(db=db)
    await vacuum(db=db)
    await drop_index(db=db)

    for mode in ["noindex", 'index']:
        await truncate(db=db)
        await vacuum(db=db)
        if mode == 'index':
            await create_index(db=db)
        else:
            await drop_index(db=db)

        for i in range(1, 81):
            await buck_create_new(db=db, epoch_count=i, count=10**6, mode=mode)
            row1 = await db.get(Article.select().limit(1))
            row2 = await db.get(Article.select().order_by(Article.created_date.desc()).limit(1))

            if mode == 'noindex':
                arv_time__noindex1 = await call_avr_time(db=db, text=row1.name)
                arv_time__noindex2 = await call_avr_time(db=db, text=row2.name)
                arv_time__noindex = max(arv_time__noindex1, arv_time__noindex2)

                logger.info(f"Time NoIndex={arv_time__noindex}")
                DATA_FOR_MATPLOTLIB[str(i)] = {"noindex": arv_time__noindex}
            else:
                arv_time__index1 = await call_avr_time(db=db, text=row1.name)
                arv_time__index2 = await call_avr_time(db=db, text=row2.name)
                arv_time__index = max(arv_time__index1, arv_time__index2)

                logger.info(f"Time Index={arv_time__index}")
                DATA_FOR_MATPLOTLIB[str(i)].update({"index": arv_time__index})

            logger.info(f"")
            now_count = await db.count(Article.select())
            logger.info(f"Row in db count = {now_count}")
            logger.info(f"==  ==  " * 15)
            logger.info(f"==  ==  " * 15)

    FileReader.write_data(DATA_FOR_MATPLOTLIB)
    logger.info(f"Exit")


if __name__ == '__main__':
    print('= = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =')
    print('= = = = = = = = = = = = = = = = = S T A R T   H W 7 = = = = = = = = = = = = = = = = = =')
    print('= = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =')

    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=10)

    loop.set_default_executor(executor)

    run(main(), stop_on_unhandled_errors=True, use_uvloop=True)
