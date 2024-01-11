"""
搜索成语的一次性脚本

通过修改 INPUT_LIMIT_LIST 来标明过滤条件
最后会输出过滤后的成语，以及各个位置的可选汉字、声母、韵母、声调，按照频次倒序

打开调试模式(DEBUG = True)可以获取更多日志

目前所有 u、ü 相关的过滤结果不保证正确，尽量不要使用
"""
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Callable

DEBUG = False  # 调试模式，会输出更详细的日志
IDIOM_JSON_FILE_NAME = "idiom.json"  # 成语 json 数据文件名，放在同级目录
IDIOM_JSON_WORD_KEY = "word"  # 成语 json 中表示成语的 key
IDIOM_JSON_PINYIN_KEY = "pinyin"  # 成语 json 中表示拼音的 key
IDIOM_MIN_LENGTH = 4  # 成语的最多字数
IDIOM_MAX_LENGTH = 4  # 成语的最多字数
PY_RIGHT_WITH_MUSIC_LIST = list("āáǎàōóǒòēéěèīíǐìūúǔùǖǘǚǜ")  # 拼音韵母带声调
PY_RIGHT_WITH_MUSIC_2_RIGHT_MUSIC: dict[str, tuple[str, int]] = {  # 拼音韵母带声调的到不带声调的映射
    rwm: ("aoeiuü"[i // 4], i % 4 + 1) for i, rwm in enumerate(PY_RIGHT_WITH_MUSIC_LIST)
}
PY_LEFT_BLANK = "-"  # - 代表没有声母
PY_ALL_LEFT_LIST = "b p m f d t n l g k h j q r x w y zh ch sh z c s".split() + [
    PY_LEFT_BLANK
]  # 拼音声母
PY_ALL_LEFT_SET = set(PY_ALL_LEFT_LIST)  # 拼音声母
PY_ALL_RIGHT_LIST = (  # 拼音韵母
    "a ai an ang ao "
    "e ei en eng er "
    "i ia ian iang iao ie in ing io iong iu "
    "o ong ou "
    "u ua uai uan uang ui un uo "
    "ü üan üe ün"
).split()
PY_ALL_RIGHT_SET = set(PY_ALL_RIGHT_LIST)
INPUT_LIMIT_LIST: list[str] = [  # 限制
    # [汉字/声母/韵母/01234声调] [c01234? 数量] [p1234 位置]
    # "iang c0",  # 没有 iang 这个韵母
    # "好 c?",  # 有 好 这个字，但不知道有几个
    # "2 c1 p2",  # 在第二个位置是二声
    # "2 c0 p2",  # 在第二个位置不能是 2 声
    # "- c1 p4",  # 第四个位置没有声母
    # 1
    "y c0"
    # 2
]
INPUT_LIMIT_TAG_MUSIC_LIST = list("01234")  # 限制中表示声调的，0 代表轻声
INPUT_LIMIT_TAG_COUNT = "c"  # 限制中表示数量
INPUT_LIMIT_TAG_POSITION = "p"  # 限制中表示位置
INPUT_LIMIT_TAG_COUNT_VAL_MIN1 = "?"  # 限制中表示数量至少一个的值
INPUT_LIMIT_TAG_COUNT_VAL_LIST = [str(c) for c in range(IDIOM_MAX_LENGTH + 1)] + [
    str(INPUT_LIMIT_TAG_COUNT_VAL_MIN1)
]  # 限制中表示数量的值
INPUT_LIMIT_TAG_POSITION_VAL_LIST = [
    str(p) for p in range(1, IDIOM_MAX_LENGTH + 1)
]  # 限制中表示位置的值
OUTPUT_IDIOM_MAX_COUNT = 50  # 输出备选成语时，最多这么多个
OUTPUT_WORD_MAX_COUNT = 50  # 输出某位置的备选汉字时，最多这么多个


def log(level: int, *args, **kwargs):
    if level < logging.INFO and not DEBUG:
        return

    print(*args, **kwargs)


def log_info(*args, **kwargs):
    log(logging.INFO, *args, **kwargs)


def log_debug(*args, **kwargs):
    log(logging.DEBUG, *args, **kwargs)


def loads_idiom() -> list[dict]:
    log_debug("开始加载全量成语数据...")
    log_debug(f"配置的成语最少字数是：{IDIOM_MIN_LENGTH}")
    log_debug(f"配置的成语最多字数是：{IDIOM_MAX_LENGTH}")

    current_directory = Path(__file__).resolve().parent
    file_path = current_directory / IDIOM_JSON_FILE_NAME

    with open(file_path, "r") as f:
        origin_idiom_list: list[dict] = json.load(f)
        if not isinstance(origin_idiom_list, list):
            log_debug("origin_idiom_list 数据类型不对")
            origin_idiom_list = []

    word_set = set()
    idiom_list = []
    for i, idiom in enumerate(origin_idiom_list):
        if not isinstance(idiom, dict):
            log_debug(f"第 {i} 个成语数据类型不对")
            continue
        if not (word := idiom.get(IDIOM_JSON_WORD_KEY)):
            log_debug(f"第 {i} 个成语没有词语内容")
            continue
        if not isinstance(word, str):
            log_debug(f"第 {i} 个成语的词语 {word} 不对")
            continue
        if not IDIOM_MIN_LENGTH <= len(word) <= IDIOM_MAX_LENGTH:
            continue
        if word in word_set:
            log_debug(f"第 {i} 个成语的词语 {word} 重复了")
            continue
        if not (pinyin_total := idiom.get(IDIOM_JSON_PINYIN_KEY)):
            log_debug(f"第 {i} 个成语的拼音 {pinyin_total} 不对")
            continue
        pinyin_list = pinyin_total.split()
        if not IDIOM_MIN_LENGTH <= len(pinyin_list) <= IDIOM_MAX_LENGTH:
            log_debug(f"成语 {word} 的拼音 {pinyin_total} 不对")
            continue

        py_left_list = []
        py_right_list = []
        py_music_list = []
        for pinyin in pinyin_list:
            if pinyin[:2] in PY_ALL_LEFT_SET:
                py_left = pinyin[:2]
                py_right = pinyin[2:]
            elif pinyin[:1] in PY_ALL_LEFT_SET:
                py_left = pinyin[:1]
                py_right = pinyin[1:]
            else:
                py_left = PY_LEFT_BLANK
                py_right = pinyin

            if py_right in PY_ALL_RIGHT_SET:
                music = 0
            else:
                if py_right and py_right[0] in PY_RIGHT_WITH_MUSIC_2_RIGHT_MUSIC:
                    py_right_wait_replace = py_right[0]
                elif (
                    len(py_right) > 1
                    and py_right[1] in PY_RIGHT_WITH_MUSIC_2_RIGHT_MUSIC
                ):
                    py_right_wait_replace = py_right[1]
                else:
                    log_debug(f"成语 {word} 的拼音 {pinyin_total} 里面的 {pinyin} 不对")
                    break
                py_right_to_replace, music = PY_RIGHT_WITH_MUSIC_2_RIGHT_MUSIC[
                    py_right_wait_replace
                ]
                py_right = py_right.replace(py_right_wait_replace, py_right_to_replace)
            if py_right == "ue":
                py_right = "üe"
            if py_right not in PY_ALL_RIGHT_SET:
                log_debug(f"成语 {word} 的拼音 {pinyin_total} 里面的 {py_right} 不对")
                break

            py_left_list.append(py_left)
            py_right_list.append(py_right)
            py_music_list.append(music)

        if len(py_left_list) != len(pinyin_list):
            continue

        idiom_list.append(
            {
                "word": word,
                "pinyin": pinyin_total,
                "py_left_list": py_left_list,
                "py_right_list": py_right_list,
                "py_music_list": py_music_list,
            }
        )

    log_debug(f"全量成语数据加载完毕，总数: {len(idiom_list)}")
    return idiom_list


def loads_limit() -> list[str]:
    log_debug("开始解析限制...")
    limit_list = []
    for input_limit in INPUT_LIMIT_LIST:
        input_limit = input_limit.strip()
        if not input_limit:
            continue
        tag_list = input_limit.split()
        if not 2 <= len(tag_list) <= 3:
            log_debug(f"limit {input_limit} 中的参数数量不对")
            continue
        if not (val := tag_list[0]):
            log_debug(f"limit {input_limit} 值是空的")
            continue
        if val.isdigit() and val not in INPUT_LIMIT_TAG_MUSIC_LIST:
            log_debug(f"limit {input_limit} 值是非法音调")
            continue
        if len(val) > 1 and val not in PY_ALL_LEFT_SET and val not in PY_ALL_RIGHT_SET:
            log_debug(f"limit {input_limit} 值是非法声母/韵母")
            continue
        if not (count_tag := tag_list[1]):
            log_debug(f"limit {input_limit} 数量标记是空的")
            continue
        if not count_tag.startswith(INPUT_LIMIT_TAG_COUNT):
            log_debug(f"limit {input_limit} 数量标记开头不对")
            continue
        if count_tag[1:] not in INPUT_LIMIT_TAG_COUNT_VAL_LIST:
            log_debug(f"limit {input_limit} 数量值不对")
            continue
        if len(tag_list) == 3:
            if not (posi_tag := tag_list[2]):
                log_debug(f"limit {input_limit} 位置标记是空的")
                continue
            if not posi_tag.startswith(INPUT_LIMIT_TAG_POSITION):
                log_debug(f"limit {input_limit} 位置标记开头不对")
                continue
            if posi_tag[1:] not in INPUT_LIMIT_TAG_POSITION_VAL_LIST:
                log_debug(f"limit {input_limit} 位置值不对")
                continue

        limit_list.append(input_limit)

    log_debug(f"共解析到 {len(limit_list)} 条限制")
    return limit_list


def limit_2_check_func(limit: str) -> Callable[[dict], bool]:
    tag_list = limit.split()
    if len(tag_list) == 2:
        val, count_tag = tag_list
        posi_tag = ""
    else:
        val, count_tag, posi_tag = tag_list

    if val.isdigit():
        idiom_key = "py_music_list"
        val = int(val)
    elif val in PY_ALL_LEFT_SET:
        idiom_key = "py_left_list"
    elif val in PY_ALL_RIGHT_SET:
        idiom_key = "py_right_list"
    else:
        idiom_key = "word"

    if count_tag[1:] == INPUT_LIMIT_TAG_COUNT_VAL_MIN1:
        count_min = 1
        count_max = IDIOM_MAX_LENGTH
    else:
        count_min = count_max = int(count_tag[1:])

    if posi_tag:
        posi = int(posi_tag[1:])
        posi_slice = slice(posi - 1, posi)
    else:
        posi_slice = slice(None, None)

    log_debug(
        f"【{limit}】生成过滤函数：{count_min=}, {count_max=}, {val=}, {idiom_key=}, {posi_slice=}"
    )
    return (
        lambda idiom: count_min
        <= sum(v == val for v in idiom[idiom_key][posi_slice])
        <= count_max
    )


def output_result_idiom_list(idiom_list: list[dict]):
    log_info(f"剩余可选成语({len(idiom_list)}个): ")
    for i in range(0, min(len(idiom_list), OUTPUT_IDIOM_MAX_COUNT), 4):
        log_info("    ", end="")
        for idiom in idiom_list[i : min(i + 4, OUTPUT_IDIOM_MAX_COUNT)]:
            idiom_show = f"{idiom['word']}  {idiom['pinyin']}"
            log_info(f"{idiom_show:<30}", end="")
        log_info()

    posi_choice_count_list = [
        {
            "char_count": defaultdict(int),
            "py_left_count": defaultdict(int),
            "py_right_count": defaultdict(int),
            "py_music_count": defaultdict(int),
        }
        for _ in range(IDIOM_MAX_LENGTH)
    ]
    idiom_key_2_choice_key = {
        "word": "char_count",
        "py_left_list": "py_left_count",
        "py_right_list": "py_right_count",
        "py_music_list": "py_music_count",
    }
    for idiom in idiom_list:
        for idiom_key, choice_key in idiom_key_2_choice_key.items():
            for posi in range(IDIOM_MAX_LENGTH):
                posi_choice_count_list[posi][choice_key][idiom[idiom_key][posi]] += 1

    output_control_list: list[tuple[str, str, str, int]] = [
        ("汉字", "char_count", "", OUTPUT_WORD_MAX_COUNT),
        ("声母", "py_left_count", " ", -1),
        ("韵母", "py_right_count", " ", -1),
        ("声调", "py_music_count", "", -1),
    ]
    for posi, posi_choice in enumerate(posi_choice_count_list):
        log_info(f"位置 {posi + 1} 可选（按频次倒序）: ")
        for name, key, join_str, count_limit in output_control_list:
            val_count_sorted = sorted(posi_choice[key].items(), key=lambda i: -i[1])
            if len(val_count_sorted) > 2:
                max_count_val_msg = f"，最高频次为 {val_count_sorted[0][1]}"
            else:
                max_count_val_msg = ""
            log_info(
                f"    {name}(共 {len(posi_choice[key])} 个{max_count_val_msg}): ", end=""
            )

            if count_limit != -1:
                val_count_sorted = val_count_sorted[:count_limit]
            log_info(join_str.join(str(i[0]) for i in val_count_sorted))


def main():
    idiom_list = loads_idiom()
    limit_list = loads_limit()
    check_func_list = [limit_2_check_func(limit) for limit in limit_list]

    result_idiom_list = []
    if check_func_list:
        for idiom in idiom_list:
            for check_func in check_func_list:
                if not check_func(idiom):
                    break
            else:
                result_idiom_list.append(idiom)
    else:
        result_idiom_list = idiom_list[:]

    output_result_idiom_list(result_idiom_list)


if __name__ == "__main__":
    main()
