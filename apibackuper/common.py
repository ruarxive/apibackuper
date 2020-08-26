# coding: utf-8

def get_dict_value(adict, key, prefix=None):
    if prefix is None:
        prefix = key.split('.')
    if len(prefix) == 1:
        return adict[prefix[0]]
    else:
        return get_dict_value(adict[prefix[0]], key, prefix=prefix[1:])
