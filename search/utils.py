
def comma_splitter(text, indexing=False, **kwargs):
    """ Comma delimited list splitter"""
    if not text:
        return []
    
    keywords = []
    for word in set(text.split(',')):
        if not word:
            continue
        else:
            keywords.append(word.strip().lower())

    return keywords

