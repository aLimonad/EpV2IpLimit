"""
This module checks if a user (name and IP address)
appears more than two times in the ACTIVE_USERS list.
"""

import asyncio
from collections import Counter

from telegram_bot.send_message import send_logs
from utils.logs import logger
from utils.panel_api import disable_user
from utils.panel_api import send_notify_request
from utils.read_config import read_config
from utils.types import PanelType, UserType

ACTIVE_USERS: dict[str, UserType] | dict = {}

# Глобальный счётчик для отслеживания вызовов
CALL_COUNTER = 0

async def check_ip_used() -> dict:
    """
    This function checks if a user (name and IP address)
    appears more than two times in the ACTIVE_USERS list.
    """
    # pylint: disable=global-statement
    global CALL_COUNTER

    all_users_log = {}
    for email in list(ACTIVE_USERS.keys()):
        data = ACTIVE_USERS[email]
        ip_counts = Counter(data.ip)
        data.ip = list({ip for ip in data.ip if ip_counts[ip] > 2})
        all_users_log[email] = data.ip
        logger.info(data)

    total_ips = sum(len(ips) for ips in all_users_log.values())
    all_users_log = dict(
        sorted(
            all_users_log.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )
    )

    config_data = await read_config()
    enable_statistic = config_data.get(
        "PANEL_ENABLE_STATISTIC", 0
    )  # По умолчанию 0, если ключ отсутствует

    missed_count = config_data.get(
        "PANEL_MISSED_COUNT", 0
    )  # По умолчанию 0, если ключ отсутствует

    # Увеличиваем счётчик при каждом вызове
    CALL_COUNTER += 1

    # Проверяем, если enable_statistic == 1 и счётчик достиг 20
    if enable_statistic == 1 and (missed_count == 0 or CALL_COUNTER % missed_count == 0):
        messages = []
        logger.info("Number of all active ips: %s", str(total_ips))
        messages.append(f"Count Of All Active IPs: <b>{total_ips}</b>")
        messages.append("<code>ElbrusProxy corp.</code>")

        await send_logs(messages)

    return all_users_log

async def check_users_usage(panel_data: PanelType):
    """
    checks the usage of active users
    """
    config_data = await read_config()
    all_users_log = await check_ip_used()
    except_users = config_data.get("EXCEPT_USERS", [])
    special_limit = config_data.get("SPECIAL_LIMIT", {})
    limit_number = config_data["GENERAL_LIMIT"]
    for user_name, user_ip in all_users_log.items():
        if user_name not in except_users:
            user_limit_number = int(special_limit.get(user_name, limit_number))
            if len(set(user_ip)) > user_limit_number:
                message = (
                    f"User {user_name} has {str(len(set(user_ip)))}"
                    + f" active ips. {str(set(user_ip))}"
                )
                logger.warning(message)
                await send_logs(str("<b>Warning: </b>" + message))
                try:
                    await disable_user(panel_data, UserType(name=user_name, ip=[]))
                    await send_notify_request(panel_data, UserType(name=user_name, ip=[]))
                except ValueError as error:
                    print(error)
    ACTIVE_USERS.clear()
    all_users_log.clear()


async def run_check_users_usage(panel_data: PanelType) -> None:
    """run check_ip_used() function and then run check_users_usage()"""
    while True:
        await check_users_usage(panel_data)
        data = await read_config()
        await asyncio.sleep(int(data["CHECK_INTERVAL"]))
