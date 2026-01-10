class PriceConverter:
    @staticmethod
    def to_int(price_str):
        if not price_str: return 0
        try:
            val = price_str.replace(",", "").strip()
            if "억" in val:
                parts = val.split("억")
                eok = int(parts[0]) if parts[0] else 0
                man = int(parts[1].replace("만", "")) if len(parts) > 1 and parts[1] else 0
                return eok * 10000 + man
            elif "만" in val:
                return int(val.replace("만", ""))
            elif val.isdigit():
                return int(val)
        except ValueError:
            pass
        return 0

    @staticmethod
    def to_string(price_int):
        if price_int == 0: return "0"
        eok = price_int // 10000
        man = price_int % 10000
        if eok > 0 and man > 0:
            return f"{eok}억 {man}만"
        elif eok > 0:
            return f"{eok}억"
        else:
            return f"{man}만"

class AreaConverter:
    PYEONG_RATIO = 0.3025

    @classmethod
    def sqm_to_pyeong(cls, sqm):
        return round(float(sqm) * cls.PYEONG_RATIO, 1)

    @classmethod
    def pyeong_to_sqm(cls, pyeong):
        return round(float(pyeong) / cls.PYEONG_RATIO, 2)
