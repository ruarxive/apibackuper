from bs4 import BeautifulSoup
def process(html_doc):
    soup = BeautifulSoup(html_doc, 'html.parser')
    response = {}
#    print(html_doc)
    response['data'] = []
    try:
        response['total'] = int(soup.find('span', attrs={'class' : "col_oz"}).string[1:-1]) 
    except AttributeError:
        response['total'] = 0
        return response
    table = soup.find('table', attrs={'class' : 'tbl_search_results table table-hover mb0 table_input table_input_sk graggable_table'})
    objects = table.findAll('tr')
    for o in objects[1:]:
        num_obj = o.find('div', attrs={'class' : "o_top"})        
        if 'data-law_number' in num_obj.attrs.keys(): 
            num = num_obj.attrs['data-law_number']
            record = {'num' : num, 'url' : 'https://sozd.duma.gov.ru/bill/' + num }
            cells = o.findAll('td')
            record['name'] = cells[1].find('div', attrs={'class' : 'fw500'}).string
            record['date_reg'] = cells[2].string
            record['initiator'] = ' '.join([r.text.strip() for r in cells[3].findAll('div')])
            record['date_lastaction'] = cells[5].string  
            response['data'].append(record)
        else:
            continue
    print(len(response['data']))
    return response