def rotate(li: list, x: int) -> list:
    return li[-x % len(li):] + li[:-x % len(li)]


def all_rotations(li: list) -> list[list]:
    return [rotate(li, x) for x in range(len(li))]


def merge_sort(left: list, right: list) -> list:
    return sorted(set(left + right))
