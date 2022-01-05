from datetime import datetime, date


def serialize(v):
    t = type(v)
    if t == str:
        return v
    elif t == type(None):
        return ""
    elif t == bool:
        return str(int(v))
    elif t == float:
        return str(round(v, 4))
    elif t == int:
        return str(v)
    elif t == datetime or t == date:
        return v.isoformat()
    else:
        print("WARNING: unknown type", t, "for", v)
        return str(v)


def write_csv(path, lines, headers=None):
    lines = list(lines)
    if not lines:
        print(f"WARNING: no lines to write to csv {path}")

    f = open(path, 'w') if path else None

    # write provided headers first, in order, then rest of keys in alphabetical order
    existing_headers = set()
    for line in lines:
        existing_headers.update(line.keys())
    headers = headers + sorted(existing_headers.difference(set(headers)))
    print(",".join(headers), file=f)

    for line in lines:
        print(",".join(map(lambda h: serialize(line.get(h, None)), headers)), file=f)

    if f:
        f.close()

    return headers


if __name__ == "__main__":

    def jam():
        yield {'a': 1, 'b': 2, 'd': 3, 'c': 4}
        yield {'a': 1, 'b': 2, 'd': 3, 'c': 5}

    write_csv('/tmp/james.csv',
              jam(), ['d', 'b'])

    expected_str = "d,b,a,c\n"
    expected_str += "3,2,1,4\n"
    expected_str += "3,2,1,5\n"

    output_csv_content = open('/tmp/james.csv').read()

    assert expected_str == output_csv_content
