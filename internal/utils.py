import functools
import re
import string


class FuzzyMatcher:
    preproc = str.maketrans(
        string.ascii_lowercase, string.ascii_uppercase, string.whitespace
    )

    def __init__(self, target: str):
        target = target.translate(self.preproc)
        chars = set(map(ord, target))
        mex = min(set(range(len(chars) + 1)) - set(chars))

        self.target = target
        self.bad = chr(mex)  # a character not in the target string
        self.regex = re.compile(f"[^{target}]")

    def normalize(self, s: str):
        s = s.translate(self.preproc)
        s = self.regex.sub(self.bad, s)
        return s

    @classmethod
    @functools.lru_cache
    def edit_distance(cls, a: str, b: str, threshold: int):
        dp = list(range(len(b) + 1))
        for i in range(len(a)):
            dp[0] = i
            for j in reversed(range(len(b))):
                dp[j + 1] = min(dp[j] + (a[i] != b[j]), dp[j + 1] + 1)
            for j in range(len(b)):
                dp[j + 1] = min(dp[j + 1], dp[j] + 1)
            if min(dp) > threshold:
                return threshold + 1
        return dp[-1]

    def match(self, s: str, threshold: int):

        processed = self.normalize(s)
        for i in range(len(processed)):
            subtext = processed[i : i + len(self.target)]
            if subtext.count(self.bad) > threshold:
                continue

            if self.edit_distance(subtext, self.target, threshold) <= threshold:
                index_mapping = [
                    i for i, ch in enumerate(s) if ch not in string.whitespace
                ]
                start = index_mapping[i]
                end = index_mapping[i + len(subtext) - 1] + 1
                return start + 1, s[start:end]
        return None
