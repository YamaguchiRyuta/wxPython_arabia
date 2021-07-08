# coding: utf-8
import re
import copy
import random
import time


def document_it(func):
    def new_function(*args, **kwargs):
        print('-' * 40)
        print('Running function:', func.__name__)
        t1_start = time.perf_counter()
        result = func(*args, **kwargs)
        t1_stop = time.perf_counter()
        print("Elapsed time:", t1_stop - t1_start, "[sec]")
        print('-' * 40)
        return result
    return new_function


class Kansuji2Arabic(object):
    """漢数字⇒アラビア数字への変換クラス"""
    def __init__(self):
        self.new_word = ""
        self.update_lattice_ids = []
        self.before_word = ""
        self.before_word2 = ""

        self.insert_space = False
        self.before_first_id = ""

        self.return_lattice = None
        self.speaker = 1

        self.omit_list1 = ["第"]
        self.omit_list2 = ["章", "段"]

        self.force_trans = False

        self.setting = {}
        try:
            with open("arabia_ng.json", mode="r", encoding="utf-8") as f:
                self.setting = json.load(f)
                self.setting["除外単語"] = list(set(self.setting["除外単語"]))
                self.setting["単位"] = "".join(set(list(self.setting["単位"])))
        except Exception as err:
            self.setting = {
                "除外単語": [],
                "単位": ""
            }

    # @document_it
    def execute(self, lattice_obj, force_trans=False):
        self.force_trans = force_trans
        word = "一二三四五六七八九〇零十百千０１２３４５６７８９"
        target_list = re.compile('[' + word + ']')

        # tt_ksuji = str.maketrans('1234567890', '１２３４５６７８９０')

        # 引数で渡されたLatticeをごっそりコピー。copy.deepcopy()を使うと参照渡しじゃなくなる。
        self.return_lattice = copy.deepcopy(lattice_obj)

        # 各話者ごとにLatticeを読み込む
        for self.speaker, lattices in lattice_obj.items():
            # 一時変数のクリア
            self.temp_value_clear()
            self.insert_space = False
            self.before_first_id = ""

            # Latticeの単語を順次読み込む
            for current_id, current_data in sorted(lattices.items(),
                                                   key=lambda x: float(x[1]["start"])):
                # current_word = current_data["word"].translate(tt_ksuji)
                current_word = current_data["word"]
                # 対象となる文字を正規表現で検索
                kansuji = target_list.findall(current_word)
                # not_allow = not_allow_list.findall(current_word)

                # 1秒未満の!NULLは無視する
                if current_word in ["!NULL", "!ENTER", "!EXIT"]:
                    word_time_length = float(current_data["end"]) - float(current_data["start"])
                    if word_time_length >= 1:
                        self.update_return_lattice()
                        self.insert_space = False
                    continue

                # todo: 除外単語の処理
                # １文字ずつprocess_digit()に渡す
                for x in current_word:
                    # 一時変数と現在の単語から、適切な単位で区切った上でアラビア変換する
                    self.process_digit(current_word=x, current_id=current_id)
                continue
            # 話者の単語を全て読み込んだ後、一時変数に値が残っていた場合はLatticeを更新してから次の話者へ
            if self.new_word:
                self.update_return_lattice()

        # 「第」の後のアラビア数字か、「段、章」の前のアラビア数字を漢数字へ戻す
        # self.arabic2kansuji()

        # 可能であれば「点」「、」を小数点にする
        self.ten2period()

        self.lattice_one_subst()

        self.lattice_space_edit()

        return self.return_lattice

    def process_digit(self, current_word, current_id):
        """一時変数と現在の単語から、適切な単位で区切った上でアラビア変換するためのメソッド"""
        check_words = {
            "千": {
                "before_word": ["千", "百", "十", "〇", "零", "０"],
                "before_word2": ["千", "百", "十"]
            },
            "百": {
                "before_word": ["百", "十", "一", "１", "〇", "零", "０"],
                "before_word2": ["百", "十"]
            },
            "十": {
                "before_word": ["十", "一", "１", "〇", "零", "０"],
                "before_word2": ["十"]
            }
        }

        # 千、百、十の場合
        if current_word in check_words.keys():
            # １つ前の単語が 現在の単語以下の単位だった場合か１(単語が千だった場合を除く)、０だった場合は１つ前の単語まで更新
            if self.before_word in check_words[current_word]["before_word"]:
                self.update_return_lattice(current_word=current_word)
            # ２つ前の単語が 現在の単語以下の単位だった場合は２つ前の単語まで更新
            elif self.before_word2 in check_words[current_word]["before_word2"]:
                # ただし千の場合で一つ前の単語が１の場合は１つ前の単語まで更新(「一千」⇒「1000」の対応)
                if current_word == "千" and self.before_word in ["一", "１"]:
                    self.update_return_lattice(current_word=current_word)
                else:
                    self.update_return_lattice(current_word=current_word, remain2word=True)
            # 現在の単語とキーを一時変数に追加
            self.temp_value_add(current_word=current_word, update_lattice_ids=current_id)
        # １～９の場合
        elif re.findall(r'[一二三四五六七八九１２３４５６７８９]+', current_word):  # \dは全角「０」も対象になってしまう
            # １つ前の単語も１～９だった場合は１つ前の単語まで更新
            if re.findall(r'[一二三四五六七八九１２３４５６７８９]+', self.before_word):
                self.update_return_lattice(current_word=current_word)
            # 現在の単語とキーを一時変数に追加
            self.temp_value_add(current_word=current_word, update_lattice_ids=current_id)
        # 〇零０のどれか、または漢数字以外の文字の場合
        elif current_word in ["〇", "零", "０"]:
            # １つ前の単語まで更新
            self.update_return_lattice(current_word=current_word)
            # 現在の単語とキーを一時変数に追加
            self.temp_value_add(current_word=current_word, update_lattice_ids=current_id)
            # 現在の単語まで更新
            self.update_return_lattice()
        else:
            # １つ前の単語まで更新
            self.update_return_lattice(current_word=current_word)
            # 現在の単語とキーを一時変数に追加
            self.temp_value_add(current_word=current_word, update_lattice_ids=current_id)
            # 現在の単語まで更新
            self.update_return_lattice()
            self.insert_space = False

    def update_return_lattice(self, current_word="", remain2word=False):
        """Latticeの更新メソッド"""
        if self.update_lattice_ids:
            # 更新予定の先頭のLattice単語の情報を取得
            first_id = self.update_lattice_ids[0]
            first_lattice = self.return_lattice[self.speaker][first_id]

            # 更新予定の最後のLattice単語の情報を取得
            if len(self.update_lattice_ids) > 1:
                if remain2word:
                    last_id = self.update_lattice_ids[-2]
                else:
                    last_id = self.update_lattice_ids[-1]
                last_lattice = self.return_lattice[self.speaker][last_id]
                # first_lattice["end"] = last_lattice["end"]

            # 前回更新時の先頭IDが異なる場合は全IDの単語を!NULLにする
            if self.before_first_id != first_id:
                for i in self.update_lattice_ids:
                    # del self.return_lattice[self.speaker][i]
                    self.return_lattice[self.speaker][i]["word"] = "!NULL"
            # 前回更新時の先頭IDが同じ場合は先頭ID以外の単語を!NULLにする
            else:
                for i in self.update_lattice_ids[1:]:
                    # del self.return_lattice[self.speaker][i]
                    self.return_lattice[self.speaker][i]["word"] = "!NULL"

            # ２つ前の単語まで更新する場合はアラビア変換を行う文字列の末尾は除外
            if remain2word:
                arabia_word = self.kansuji2arabic(self.new_word[:-1],
                                                  current_word=current_word,
                                                  remain2word=remain2word)
            # １つ前の単語まで更新する場合は全文字列でアラビア変換を行う
            else:
                arabia_word = self.kansuji2arabic(self.new_word,
                                                  current_word=current_word,
                                                  remain2word=remain2word)

            # 更新しようとしているLatticeの単語が!NULLだった場合はアラビア数字で上書き
            if self.return_lattice[self.speaker][first_id]["word"] == "!NULL":
                if self.insert_space:
                    first_lattice["word"] = " " + arabia_word
                else:
                    first_lattice["word"] = arabia_word
            # 更新しようとしているLatticeの単語が!NULL以外だった場合はアラビア数字を末尾に追加
            else:
                first_lattice["word"] += " " + arabia_word

            # Latticeを更新
            self.return_lattice[self.speaker].update({first_id: first_lattice})
            # 前回更新時の先頭IDを退避
            self.before_first_id = first_id

        # 一時変数をクリア。２つ前の単語まで更新する場合は末尾１文字分の情報は残す
        self.temp_value_clear(remain2word=remain2word)
        self.insert_space = True

    def temp_value_clear(self, remain2word=False):
        """一時変数の値クリアメソッド"""
        # ２つ前の単語まで更新する場合は末尾１文字分の情報は残す
        if remain2word:
            self.new_word = self.new_word[-1]
            self.update_lattice_ids = self.update_lattice_ids[-1:]
            self.before_word = self.new_word[-1]
            self.before_word2 = ""
        else:
            self.new_word = ""
            self.update_lattice_ids = []
            self.before_word = ""
            self.before_word2 = ""

    def temp_value_add(self, current_word="", update_lattice_ids=None):
        """一時変数への値追加メソッド"""
        if update_lattice_ids is None:
            update_lattice_ids = []

        self.new_word += current_word

        # 更新予定のIDが既に登録されていた場合は追加しない
        if update_lattice_ids not in self.update_lattice_ids:
            self.update_lattice_ids.append(update_lattice_ids)

        self.before_word2 = self.before_word
        self.before_word = current_word

    def kansuji2arabic(self, word, current_word="", remain2word=False, sep=False):
        """渡された文字列をアラビア数字へ変換して返すメソッド。sep=Trueで３桁ごとにカンマを付ける。
        「十百千」のような文字列を渡すと「1110」になってしまうため、このメソッドに渡す文字列は
        単位を考慮し適切に加工する必要がある。
        """
        not_allow_list = re.compile(r'[^一二三四五六七八九〇零十百千億万兆点、.。\d' +
                                    r'あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほ' +
                                    r'まみむめもやゆよらりるれろわをんがぎぐげござじずぜぞだぢづでど' +
                                    r'ばびぶべぼぱぴぷぺぽぁぃぅぇぉゃゅょっ' +
                                    r'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホ' +
                                    r'マミムメモヤユヨラリルレロワヲンガギグゲゴザジズゼゾダヂヅデド' +
                                    r'バビブベボパピプペポァィゥェォャュョッ a-zA-Z'
                                    + self.setting['単位'] +
                                    ']')
        if remain2word:
            current_word = self.new_word[-1]

        if not self.force_trans and len(not_allow_list.findall(current_word)) > 0:
            return word
        # 数字系の文字を全て半角数字に変換
        tt_ksuji = str.maketrans('一二三四五六七八九〇零１２３４５６７８９０',
                                 '123456789001234567890')
        transuji = word.translate(tt_ksuji)

        re_suji = re.compile(r'[十百千\d]+')
        # 連続した十百千または数字の中から文字数の長い順に処理
        for suji in sorted(set(re_suji.findall(transuji)), key=lambda s: len(s), reverse=True):
            # isdecimalはローマ数字または漢数字の場合にFalseになる。
            # ちなみにisdigit()では漢数字の場合にFalseになる。
            text = ''
            if not suji.isdecimal():
                for suji_div in re.findall(re_suji, suji):
                    result = self.trans_value(suji_div)
                    text += '{:,}'.format(result) if sep else str(result)
            if text:
                transuji = transuji.replace(suji, text)
        return transuji

    @staticmethod
    def trans_value(sj):
        """単位に合わせてアラビア数字に変換するメソッド"""
        trans_unit = {'十': 10,
                      '百': 100,
                      '千': 1000}
        unit = 1
        result = 0
        for piece in reversed(re.findall(r'[十百千]|\d+', sj)):
            if piece in trans_unit:
                if unit > 1:
                    result += unit
                unit = trans_unit[piece]
            else:
                # piece.isdecimal()がTrueになるのは全てアラビア数字の時。(半角全角問わず)
                val = int(piece)
                result += val * unit
                unit = 1
        if unit > 1:
            result += unit
        return result

    def arabic2kansuji(self):
        """アラビア数字から漢数字に戻すメソッド"""

        temp_lattice = {}
        # Latticeから!NULLと空白を除去して一時的なLatticeを作る
        for speaker, lattices in self.return_lattice.items():
            temp_lattice.setdefault(speaker, {})
            for current_id, current_data in lattices.items():
                if current_data["word"] not in ["!NULL", "!ENTER", "!EXIT"] and current_data["word"].replace(" ", "") != "":
                    temp_lattice[speaker].setdefault(current_id, current_data)

        # 一時的なLatticeのID一覧を作成
        for speaker, lattices in self.return_lattice.items():
            arabic2kansuji_ids = []
            arabic2kansuji_flag = False

            # Latticeの単語を順次読み込む
            for i, (current_id, current_data) in enumerate(
                    sorted(lattices.items(), key=lambda x: float(x[1]["start"]))):
                current_word = current_data["word"]

                # 読み込んだ単語が 章 段 だった場合
                if current_word in self.omit_list2:
                    # 退避したIDの単語を漢数字に戻す
                    if arabic2kansuji_ids:
                        self.trans_omit(arabic2kansuji_ids, speaker)
                    arabic2kansuji_flag = False
                    arabic2kansuji_ids = []
                else:
                    # 読み込んだ単語が 第 だった場合
                    if current_word in self.omit_list1:
                        # 読み込んだ単語より前に既に 第 があった場合は退避したIDの単語を漢数字に戻す
                        if arabic2kansuji_flag and arabic2kansuji_ids:
                            self.trans_omit(arabic2kansuji_ids, speaker)
                        arabic2kansuji_flag = True
                        arabic2kansuji_ids = []
                    # !NULLは一旦アラビア数字と同じ扱いにし、漢数字に戻す処理内で無視する。
                    elif current_word in ["!NULL", "!ENTER", "!EXIT"]:
                        # IDを退避
                        arabic2kansuji_ids.append(current_id)
                    else:
                        skip = False
                        try:
                            # 単語内の文字のスペースを除去し、int型に変換できるかチェック
                            for x in current_word.split():
                                int(x)
                                if len(x) > 4 or x in self.setting['除外単語']:
                                    # 4桁以上ならスキップ
                                    skip = True
                        # int型に変換できないならアラビア数字ではないと判断しスキップ
                        except ValueError:
                            skip = True
                        # IDを退避
                        if not skip:
                            arabic2kansuji_ids.append(current_id)
                        else:
                            # スキップした場合
                            # 読み込んだ単語より前に 第 があった場合は退避したIDの単語を漢数字に戻す
                            if arabic2kansuji_flag and arabic2kansuji_ids:
                                self.trans_omit(arabic2kansuji_ids, speaker)
                            arabic2kansuji_flag = False
                            arabic2kansuji_ids = []
            # 話者の単語を全て読み込んだ後、前に 第 がある、かつ退避したIDが残っている場合は漢数字に戻す
            if arabic2kansuji_flag and arabic2kansuji_ids:
                self.trans_omit(arabic2kansuji_ids, speaker)

    def trans_omit(self, arabic2kansuji_ids, speaker):
        tt_ksuji = str.maketrans('1234567890', '一二三四五六七八九〇')
        tanni = {
            0: "",
            1: "十",
            2: "百",
            3: "千"
        }

        # 退避したIDの単語を順に読み込む
        for reverse_id in arabic2kansuji_ids:
            # 単語をスペースで区切る
            words = self.return_lattice[speaker][reverse_id]["word"].split()
            # 区切った結果の長さが0または!NULLがあった場合はスキップ
            if len(words) == 0 or words in ["!NULL", "!ENTER", "!EXIT"]:
                continue
            temp = ""
            # 区切った単語を順に読み込む
            for i, word in enumerate(words):
                word_length = len(word)
                output = ""
                # 1桁の場合
                if word_length == 1:
                    # 単語の0～9を〇～九に置換
                    output = word.translate(tt_ksuji)
                # 2桁以上の場合
                else:
                    # 単語の0～9を〇～九に置換
                    word = word.translate(tt_ksuji)
                    # 単語を末尾から順に１文字ずつ読み込む
                    for i, reverse_word in enumerate(reversed(word)):
                        # 1の位
                        if i == 0:
                            output = reverse_word if reverse_word != "〇" else ""
                        # 10以上の位
                        else:
                            if reverse_word == "一":
                                output = tanni[i] + output
                            elif reverse_word != "〇":
                                output = reverse_word + tanni[i] + output
                temp += output
            # 漢数字に戻したら、Latticeを更新
            self.return_lattice[speaker][reverse_id]["word"] = temp

    def ten2period(self):
        """可能であれば「点」「、」を小数点「.」に置き換えるメソッド"""
        keys = {}
        temp_lattice = {}
        # Latticeから!NULLと空白を除去して一時的なLatticeを作る
        for speaker, lattices in self.return_lattice.items():
            temp_lattice.setdefault(speaker, {})
            for current_id, current_data in lattices.items():
                if current_data["word"] not in ["!NULL", "!ENTER", "!EXIT"] and current_data["word"].replace(" ", "") != "":
                    temp_lattice[speaker].setdefault(current_id, current_data)

        # 一時的なLatticeのID一覧を作成
        for speaker in range(1, len(temp_lattice) + 1):
            keys.setdefault(str(speaker), [k for k, v in sorted(
                temp_lattice.get(
                    str(speaker), {}).items(), key=lambda x: float(x[1]["start"]))])

        # 各話者ごとに一時的なLatticeを読み込む
        for speaker, lattices in temp_lattice.items():
            # 一時的なLatticeの単語を順次読み込む
            for i, (current_id, current_data) in enumerate(sorted(lattices.items(), key=lambda x: float(x[1]["start"]))):
                current_words = current_data["word"].split()
                current_words_len = len(current_words)

                # ２つ前の単語を参照
                before_key2 = keys[speaker][i - 2] if i - 2 >= 0 else ""
                # １つ前の単語を参照
                before_key = keys[speaker][i - 1] if i - 1 >= 0 else ""
                # １つ次の単語を参照
                next_key = keys[speaker][i + 1] if i + 1 <= len(keys[speaker]) - 1 else ""
                # ２つ次の単語を参照
                next_key2 = keys[speaker][i + 2] if i + 2 <= len(keys[speaker]) - 1 else ""

                temp = []
                for j, current_word in enumerate(current_words):
                    before_word2 = "!NULL"
                    before_word = "!NULL"
                    next_word = "!NULL"
                    next_word2 = "!NULL"
                    if current_word not in ["、", "点"]:
                        temp.append(current_word)
                        continue

                    if j == 0:
                        if len(lattices.get(before_key, {"word": ""})["word"].split()) == 1:
                            before_word2 = lattices.get(before_key2, {"word": "!NULL"})["word"].split()[-1]
                            before_word = lattices.get(before_key, {"word": "!NULL"})["word"].split()[0]
                        elif len(lattices.get(before_key, {"word": ""})["word"].split()) >= 2:
                            before_word2 = lattices.get(before_key, {"word": "!NULL"})["word"].split()[-2]
                            before_word = lattices.get(before_key, {"word": "!NULL"})["word"].split()[-1]
                    elif j == 1:
                        before_word2 = lattices.get(before_key, {"word": "!NULL"})["word"].split()[-1]
                        before_word = current_words[j-1]
                    elif j >= 2:
                        before_word2 = current_words[j-2]
                        before_word = current_words[j-1]

                    if j == (current_words_len - 1):
                        if len(lattices.get(next_key, {"word": ""})["word"].split()) == 1:
                            next_word = lattices.get(next_key, {"word": "!NULL"})["word"].split()[0]
                            next_word2 = lattices.get(next_key2, {"word": "!NULL"})["word"].split()[0]
                        elif len(lattices.get(next_key, {"word": ""})["word"].split()) >= 2:
                            next_word = lattices.get(next_key, {"word": "!NULL"})["word"].split()[0]
                            next_word2 = lattices.get(next_key, {"word": "!NULL"})["word"].split()[1]
                    elif j == (current_words_len - 2):
                        next_word = current_words[j+1]
                        next_word2 = lattices.get(next_key, {"word": "!NULL"})["word"].split()[0]
                    elif j <= (current_words_len - 3):
                        next_word = current_words[j + 1]
                        next_word2 = current_words[j + 2]

                    try:
                        # １つ前の単語が数値かのチェック
                        int(before_word)
                        # １つ次の単語が数値かのチェック
                        int(next_word)
                    # 数値じゃないなら次の単語へ
                    except ValueError:
                        temp.append(current_word)
                        continue
                    else:
                        # ２つ前の単語と２つ次の単語が 点 、 ではない かつ
                        # １つ次の単語が１桁の数値の場合は 点 、 を . に置換
                        if (
                            before_word2 not in ["、", "点", "."] and
                            # len(before_word) <= 3 and
                            len(next_word) == 1
                            and next_word2 not in ["、", "点", "."]
                        ):
                            temp.append(". ")
                        else:
                            temp.append(current_word)
                self.return_lattice[speaker][current_id]["word"] = " ".join(temp)

    def lattice_one_subst(self):
        # 各話者ごとに一時的なLatticeを読み込む
        for speaker, lattices in self.return_lattice.items():
            update_id = []
            break_word = False
            for current_id, current_data in sorted(lattices.items(),
                                                   key=lambda x: float(x[1]["start"])):
                for i, word in enumerate(current_data["word"].split()):
                    if word in ["!NULL", "!ENTER", "!EXIT"]:
                        word_time_length = float(current_data["end"]) - float(current_data["start"])
                        if word_time_length >= 3:
                            break_word = True
                        break

                    if len(word) != 1:
                        break_word = True
                        break
                    try:
                        int(word)
                    except ValueError:
                        break_word = True
                        break
                if (not break_word and current_id not in update_id
                        and current_data["word"] not in ["!NULL", "!ENTER", "!EXIT"]
                        and current_data["word"].replace(" ", "") != ""
                ):
                    update_id.append(current_id)
                if break_word:
                    temp = ""
                    for word_id in update_id:
                        temp += lattices[word_id]["word"] + " "
                    for i, word_id in enumerate(update_id):
                        if i == 0:
                            self.return_lattice[speaker][word_id]["word"] = temp
                        else:
                            self.return_lattice[speaker][word_id]["word"] = "!NULL"
                    update_id = []
                    break_word = False
            if update_id:
                temp = ""
                for word_id in update_id:
                    temp += lattices[word_id]["word"] + " "
                for i, word_id in enumerate(update_id):
                    if i == 0:
                        self.return_lattice[speaker][word_id]["word"] = temp
                    else:
                        self.return_lattice[speaker][word_id]["word"] = "!NULL"

    def lattice_space_edit(self):
        temp_lattice = {}
        # Latticeから!NULLと空白を除去して一時的なLatticeを作る
        for speaker, lattices in self.return_lattice.items():
            temp_lattice.setdefault(speaker, {})
            for current_id, current_data in lattices.items():
                if current_data["word"] not in ["!NULL", "!ENTER", "!EXIT"] and current_data["word"].replace(" ", "") != "":
                    temp_lattice[speaker].setdefault(current_id, current_data)

        # 各話者ごとに一時的なLatticeを読み込む
        for speaker, lattices in temp_lattice.items():
            next_len = 0
            next2period = False
            insert_space = False
            count = 0
            # 一時的なLatticeの単語を順次読み込む
            for current_id, current_data in sorted(lattices.items(),
                                                   key=lambda x: float(x[1]["start"]),
                                                   reverse=True):
                temp = ""
                # 単語を後ろから読み込む
                for word in reversed(current_data["word"].split()):
                    if word == ".":
                        next_len = 0
                        insert_space = False
                        next2period = True
                        count = 1
                        temp = word + temp
                        continue
                    try:
                        # 単語内の文字のスペースを除去し、int型に変換できるかチェック
                        int(word)
                    except ValueError:
                        next_len = 0
                        insert_space = False
                        next2period = False
                        count = 0
                        temp = word + temp
                        continue
                    # 一桁の数値が連続していたらスペースは入れない
                    if len(word) == 1 and next_len == 1 or not insert_space:
                        if next2period and count == 2:
                            temp = word + " " + temp
                            next2period = False
                            count = 0
                        else:
                            temp = word + temp
                    # 間にスペースを入れて連結
                    else:
                        temp = word + " " + temp
                    next_len = len(word)
                    insert_space = True
                    if next2period:
                        count += 1
                # Latticeを更新
                if temp:
                    self.return_lattice[speaker][current_id]["word"] = temp

    @staticmethod
    def tr_edit_lattice(lattice):
        # TRは"firstChannelLabel"ではなく"firstChannel"なので注意
        lattice_obj = lattice["channels"]["firstChannelLabel"]["lattice"]
        best_paths = {}
        keywords = []

        for lattice_name, lattice_body in lattice_obj.items():
            best_path = {}
            for (frag_id, frag) in lattice_body["links"].items():
                if frag["best_path"]:
                    if frag["word"] and frag["word"] != "!ENTER" and frag["word"] != "!NULL" and frag["word"] != "!EXIT":
                        keywords.append(frag["word"])
                    frag["word"] = frag["word"].replace("%", "%%")
                    best_path[frag_id] = frag
            best_paths[lattice_name] = best_path
        return best_paths, keywords


if __name__ == "__main__":

    test_lattice = {
        "1": {},
        "2": {}
    }

    trans = Kansuji2Arabic()
    from pprint import pprint
    flag = True

    while flag:
        for sp in range(1, 3):
            for word_index in range(0, 20):
                sample = []
                for x in '０１２３４５６７８９0123456789一二三四五六七八九〇零十百千十百千十百千万億兆億万兆月分日時秒点、点、点、 abcdefghijklmn' \
                         'あいうえおかきくけこさしすせそたちつてと':
                    sample.append(x)
                    word = ""
                    word_length = random.choice([1, 2, 3, 4])
                    # word_length = random.choice([1])
                    if word_length == 1:
                        word += random.choice(
                            [x for x in "０１２３４５６７８９0123456789一二三四五六七八九〇零十百千十百千十"
                                        "百千万億兆億万兆月分日時秒点、点、点、abcdefghijklmnあいうえお"
                                        "かきくけこさしすせそたちつてと "] + ["!NULL", "!ENTER", "!EXIT", ""])
                    else:
                        for i in range(word_length):
                            word += random.choice(sample)
                tmp = {
                        "start": word_index / 10,
                        "end": (word_index + 1) / 10,
                        "weight": 0,
                        "best_path": True,
                        "speaker": sp,
                        "word": word,
                        "intensity": 0
                    }
                test_lattice[str(sp)].update({str(word_index): tmp})

        pprint(test_lattice)
        print("-" * 15)
        test_lattice = trans.execute(test_lattice)
        # pdb.run('trans.execute(test_lattice)')
        # flag = False
        # logging.basicConfig(filename='arabic.log', level=logging.ERROR)
        # logging.error("The washing machine is leaking!")
    exit(0)

    for sp, word_indexes in test_lattice.items():
        for word_index, data in word_indexes.items():
            print(sp, word_index, data)

    # print(trans.kansuji2arabic("月払いで２億一万二千と百と三百四十五円お支払い"))

    print("-" * 15)
    import json
    import requests
    addwords = {"words_to_check": []}
    # text = '0123456789０１２３４５６７８９一二三四五六七八九〇零十百千万億兆点、章段第'
    text = '０１２３４５６７８９'
    for x in range(len(text)):
        for y in range(len(text)):
            for z in range(len(text)):
                addwords["words_to_check"].append(text[x])
                addwords["words_to_check"].append(text[y])
                addwords["words_to_check"].append(text[z])
                addwords["words_to_check"].append(text[x] + text[y])
                addwords["words_to_check"].append(text[x] + text[z])
                addwords["words_to_check"].append(text[y] + text[z])
                addwords["words_to_check"].append(text[x] + text[y] + text[z])
    addwords["words_to_check"] = list(set(addwords["words_to_check"]))
    print(len(addwords["words_to_check"]))

    addwords["words_to_check"] = ["九十九"]

    # ['0', '1', '10', '100', '10０', '1０', '1０0', '1００', '2', '3', '4', '5', '6', '7', '8', '9',
    # '、', '〇', '〇〇', '一', '一九', '一兆', '一段', '七', '万', '万一', '万万', '万八', '万六', '万十',
    # '三', '三八', '三六', '九', '九段', '二', '二十', '二十二', '五', '億', '億万', '兆', '八', '八十八',
    # '六', '十', '十一', '千', '四', '四万十', '四十万', '段', '点', '点点', '百', '章', '章一', '章三',
    # '章二', '第', '第一', '第九', '第二', '０', '１', '１0', '１00', '１0０', '１０', '１０0', '１００',
    # '２', '３', '４', '５', '６', '７', '８', '９']
    result_list = []
    temp = []
    result = {}
    count = 0
    for i, x in enumerate(addwords["words_to_check"]):
        temp.append(x)
        if not (i+1) % 5000:
            print(i+1, "/", len(addwords["words_to_check"]), len(temp), "個問い合わせ")
            result = requests.post(url="http://192.168.13.18:19901" + "/checkwords",
                                   json={"words_to_check": temp}).json()
            for y in temp:
                if result[y]["exists"] is True:
                    result_list.append(y)
            temp = []
        count += 1
    if temp:
        print(count, "/", len(addwords["words_to_check"]), len(temp), "個問い合わせ")
        result = requests.post(url="http://192.168.13.18:19901" + "/checkwords",
                               json={"words_to_check": temp}).json()
        for y in temp:
            if result[y]["exists"] is True:
                result_list.append(y)
    print(sorted(list(set(result_list))))

    # print(json.dumps(result,
    #                  indent=4,
    #                  ensure_ascii=False)
    #       )
