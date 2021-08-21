import pickle
from datetime import datetime

from common import *
from constants import *
from dc import *

CACHE = None

TIMEOUT = 5


def _get_trend(cnxpool, redis_connection=None):
    """ISUの性格毎の最新のコンディション情報"""

    """
    先にDBにあるキャラクター一覧を取って
    キャラクターごとに
    最新のコンディションを取得し、そのコンディションごとの椅子の数を求めている

    キャラクター: {
        critical: [{isu_id, last_condition_timestamp}],
        info: [],
        warn: [],
    }


    """

    data = redis_connection.get(REDIS_TREND_PREFIX)
    if data:
        return pickle.loads(data)

    # TODO 採点基準にあるか微妙なので切り捨てることもあり得るかもしれない
    query = """
        with latest_condition as (
          select
            jia_isu_uuid,
            timestamp,
            warn_count
          from
          isu_condition
          where
            (jia_isu_uuid, timestamp) in (
              select
                jia_isu_uuid,
                max(timestamp)
              from
                isu_condition
              group BY
                jia_isu_uuid
            )
        )
        select
          i.character,
          ic.warn_count,
          group_concat(
              i.id
              ORDER BY ic.timestamp desc
          ) as isu_id_list,
          group_concat(
              ic.jia_isu_uuid
              ORDER BY ic.timestamp desc
          ) as jia_isu_uuid_list,
          group_concat(
              ic.timestamp
              ORDER BY ic.timestamp desc
          ) as timestamp_list
        from
            isu i
        left outer join
            latest_condition ic
        on  i.jia_isu_uuid = ic.jia_isu_uuid

        group by
            i.character,
            ic.warn_count
        order by
            i.character,
            ic.warn_count
    """
    res = []

    # chara, wan_count分廻る
    current_character = None
    current_data = {
        'info': [],
        'warning': [],
        'critical': [],
    }
    for row in select_all(cnxpool, query):

        character = row['character']
        warn_count = row['warn_count']
        if warn_count is None:
            continue

        if current_character is None:
            current_character = character

        if character != current_character:
            res.append(
                TrendResponse(
                    character=current_character,
                    info=current_data['info'],
                    warning=current_data['warning'],
                    critical=current_data['critical'],
                )
            )

            current_character = character
            current_data = {
                'info': [],
                'warning': [],
                'critical': [],
            }

        isu_id_list = row['isu_id_list'].split(',')
        timestamp_list = row['timestamp_list'].split(',')
        for is_id, timestamp_str in zip(isu_id_list, timestamp_list):

            condition_level = warn_count_to_condition_level(warn_count)

            trend_condition = TrendCondition(
                isu_id=int(is_id),
                timestamp=int(datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S').timestamp())
            )

            current_data[condition_level].append(trend_condition)

        # character_info_isu_conditions.sort(key=lambda c: c.timestamp, reverse=True)
        # character_warning_isu_conditions.sort(key=lambda c: c.timestamp, reverse=True)
        # character_critical_isu_conditions.sort(key=lambda c: c.timestamp, reverse=True)
    # last buffer
    res.append(
        TrendResponse(
            character=current_character,
            info=current_data['info'],
            warning=current_data['warning'],
            critical=current_data['critical'],
        )
    )

    json_res = jsonify(res)
    redis_connection.set(REDIS_TREND_PREFIX, pickle.dumps(json_res), ex=TIMEOUT)
    return json_res
