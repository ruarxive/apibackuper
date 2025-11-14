# from bs4 import BeautifulSoup
import lxml.etree
import lxml.html

def taglist_to_dict(tags, fields, strip_lf=True):
    """Converts list of tags into dict"""
    has_text = TEXT_FIELD in fields
    has_tag = TAG_FIELD in fields
    finfields = fields.copy()
    data = []
    if has_text: finfields.remove(TEXT_FIELD)
    if has_tag: finfields.remove(TAG_FIELD)
    for t in tags:
        item = {}
        if has_tag:
            item[TAG_FIELD] = t.tag
        if has_text:
            item[TEXT_FIELD] = ' '.join(t.itertext()).strip()
            if strip_lf:
                item[TEXT_FIELD] = (' '.join(item[TEXT_FIELD].split())).strip()
        for f in finfields:
            item[f] = t.attrib[f].strip() if f in t.attrib.keys() else ""
        data.append(item)
    return data


def table_to_dict(node, strip_lf=True):
    """Extracts data from table"""
    data = []
    rows = node.xpath('./tbody/tr')
    if len(rows) == 0:
        rows = node.xpath('./tr')
    for row in rows:
        cells = []
        for cell in row.xpath('(./td|./th)'):
            inner_tables = cell.xpath('./table')
            if len(inner_tables) < 1:
                text = ' '.join(cell.itertext()) #cell.text_content()
                if strip_lf:
                    text = text.replace('\r',u' ').replace('\n', u' ').strip()
                cells.append(text)
            else:
                cells.append([table_to_dict(node, strip_lf) for t in inner_tables])
        data.append(cells)
    return data


KEYMAP = {'Субъект права законодательной инициативы' : 'initiator', 
          'Форма законопроекта' : 'law_form', 
          'Профильный комитет' : 'profile_comittee', 
          'Комитеты-соисполнители' : 'subcomittees',
          'Отрасль законодательства' : 'law_topic',
          'Тематический блок законопроектов' : 'law_theme',
          'Ответственный комитет' : 'responsible_comittee',
          'Срок представления поправок' : 'amendment_final_date',
          'Предмет ведения' : 'issue_assignment',
          'Вопрос ведения' : 'issue_question',
          'Принадлежность к примерной программе' : 'lawmaking_program',
          'Пакет документов при внесении' : None}  


def process(html_doc):
    hp = lxml.etree.HTMLParser(encoding='utf8')
    root = lxml.html.fromstring(html_doc, parser=hp)
    pasp_table = root.xpath('//table')[0]  
    table = table_to_dict(pasp_table)
    response = {}
    for row in table:
        if row[0] in KEYMAP.keys():
            if KEYMAP[row[0]] is not None:
                response[KEYMAP[row[0]]] = row[1]
        else:
           print(row[0])
    status = root.xpath('//span[@id="current_oz_status"]')
    if len(status) > 0:
        status = status[0].text.strip()
    else:
        status = ""
        law_num = root.xpath('//span[@data-original-title="Номер федерального закона"]')
        if len(law_num) > 0:
            response['law_num'] = law_num[0].text.strip()
            status = "Закон опубликован"
        law_url = root.xpath('//span[@data-original-title="Номер опубликования"]/a')
        if len(law_url) > 0:
            response['law_url'] = law_url[0].attrib['href']
            response['law_identifier'] = law_url[0].text.strip()
    response['status'] = status
    response['num'] = root.xpath('//span[@id="number_oz_id"]')[0].text.split()[-1]
    response['name'] = root.xpath('//span[@id="oz_name"]')[0].text.strip()
    response['documents'] = []
    doc_tags = root.xpath("//div[@class='table_icona']")    
#    print(doc_tags)
    for doc in doc_tags:
        url = doc.getparent().attrib['href']
        try:
            doc_date = doc.getparent().attrib['title'].split(' ', 1)[0]
        except:
            doc_date = ''
        format_t = doc.xpath('div[@class="table_iconatd1"]/span')
        doc_format = ''
        if len(format_t) > 0:
          doc_format = format_t[0].attrib['class'].split()[0].split('-')[-1]
        name_t = doc.xpath('div/div[@class="doc_wrap"]')
        name = ""
        if len(name_t) > 0:
            name = name_t[0].text.strip()
        response['documents'].append({'url' : url, 'name' : name, 'doc_date': doc_date, 'format' : doc_format})
    return response