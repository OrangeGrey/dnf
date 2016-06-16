#-*- coding=utf-8 -*-
from __future__ import unicode_literals
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
from collections import defaultdict
import re

AND = "AND"
OR = "OR"
IN = "IN"
NOT = "NOT"
SEP = ";"
EOF = "EOF"
ZERO = "Z"
SPACE = " "
# age:3
class Term:
    def __init__(self, key, value):
        self.key = key
        self.value = value
# age:3  in       
class Assignment:
    def __init__(self, relation, term):
        self.relation = relation
        #self.key = key
        #self.value = value
        self.term = term
        
class Conjunction:
    def __init__(self, dnf):
        self.dnf = dnf
        self.size = 0
        self.assigns = []
        self.id = 0
        
    def pushAssign(self,assign):
        self.assigns.append(assign)
    def setId(self,id):
        self.id = id
        
def parseConjunction(con):
    # con ==> age IN 3;4 AND state NOT NY
    conjunction = Conjunction(con)                
    assigns = con.split(AND)
    for ass in assigns:
        ass = ass.strip()
        
        # ass ===> age IN 3;4        
        elements = ass.split(IN)
        if len(elements) == 2:
            key = elements[0].strip()
            relation = IN
            for val in elements[1].strip().split(SEP):
                value = val.strip()
                term = Term(key, value)
                assignment = Assignment(relation, term)
                conjunction.pushAssign(assignment)
            
            conjunction.size += 1
        
        # ass ===> state NOT NY
        elements = ass.split(NOT)
        if len(elements) == 2:
            key = elements[0].strip()
            relation = NOT
            for val in elements[1].strip().split(SEP):
                value = val.strip()
                term = Term(key, value)
                assignment = Assignment(relation, term)
                conjunction.pushAssign(assignment)
    return conjunction
    
# age IN 3;4 AND state NOT NY OR state IN CA AND gender IN M 
def buildTwoLevelInvertedIndex(doc_dnf,doc_id,con_doc_inverted_index,con_id_map,ass_con_inverted_index):
    doc_dnf = re.sub('\s+',' ',doc_dnf)
    print doc_id,":",doc_dnf
    if 0 == len(doc_dnf): 
        print doc_id ," is empty !!!"
        return
    cons = doc_dnf.split(OR)
    for con in cons:
        # con ==> age IN 3;4 AND state NOT NY
        con = con.strip()
        # level two: AssignmentConjunction
        if con not in con_id_map:
            con_id = len(con_id_map) + 1
            con_id_map[con] = con_id

            conjunction = parseConjunction(con)
            conjunction.setId(con_id)
            
            for a in conjunction.assigns:
                if (a.term.key,a.term.value) not in ass_con_inverted_index[conjunction.size]:
                    ass_con_inverted_index[conjunction.size][a.term.key,a.term.value] = [(con_id,a.relation)]
                else:
                    ass_con_inverted_index[conjunction.size][a.term.key,a.term.value].append((con_id,a.relation))
                if 0 == conjunction.size:
                    if ZERO not in ass_con_inverted_index[conjunction.size]:
                        ass_con_inverted_index[conjunction.size][ZERO] = [(con_id,IN)]
                    else:
                        if (con_id,IN) not in ass_con_inverted_index[conjunction.size][ZERO]:
                            ass_con_inverted_index[conjunction.size][ZERO].append((con_id,IN))
        # level one :ConjunctionDoc
        con_doc_inverted_index[con_id_map[con]].append(doc_id)

class Plist:
    def __init__(self,key,conid_relations):
        self.key = key
        self.conid_relations = conid_relations
        self.size = len(conid_relations)
        self.current_idx = 0
        self.current_entry_id = conid_relations[0][0]
        self.current_entry_relation = conid_relations[0][1]
        
    def skipToNextId(self,nextid,defaultid):
        skip_flag = False
        if self.current_idx < self.size:
            for idx in xrange(self.current_idx,self.size,1):
                if self.conid_relations[idx][0] >= nextid:
                    self.current_idx = idx
                    self.current_entry_id = self.conid_relations[idx][0]
                    self.current_entry_relation = self.conid_relations[idx][1]
                    skip_flag = True
                    break
        if not skip_flag:
            self.current_idx = EOF
            self.current_entry_id = defaultid
            
def sortPlistByCurrentEntries(plists):
    top_key=[]
    top_plist=[]
    tail_plist=[]
    Plists = sorted(plists,key=lambda x:(x.current_entry_id,x.key[0]))

    for i in xrange(len(Plists)):
        if Plists[i].key[0] not in top_key:
            top_key.append(Plists[i].key[0])
            top_plist.append(Plists[i])
        else:
            tail_plist.append(Plists[i])
       
    top_plist.extend(tail_plist)

    return top_plist
    
def retrievalConjunctions(query,con_id_map,ass_con_inverted_index):
    query = re.sub('\s+',' ',query)
    print "query:",query
    fit_cons = set()

    # query ==> age IN 3 AND state IN CA AND gender IN M
    query = query.strip()
    conjunction = parseConjunction(query)    
    if 0 == len(conjunction.assigns):
        return fit_cons
         
    size = min(max(ass_con_inverted_index.keys()),conjunction.size)
    for K in xrange(size,-1,-1):
        Plists = []
        for ass in conjunction.assigns:
            key = (ass.term.key, ass.term.value)
            if key in ass_con_inverted_index[K]:
                value = ass_con_inverted_index[K][key]                   
                plist = Plist(key,value) 
                Plists.append(plist)
        Plists = sortPlistByCurrentEntries(Plists)
        if K == 0: K=1
        if len(Plists) < K: continue

        while Plists[K-1].current_idx != EOF:
            Plists = sortPlistByCurrentEntries(Plists)
            if Plists[0].current_entry_id == Plists[K-1].current_entry_id:          
                if Plists[0].current_entry_relation == NOT or Plists[K-1].current_entry_relation == NOT:
                    RejectId = Plists[0].current_entry_id
                    for L in xrange(K-1,len(Plists)):
                        if Plists[L].current_entry_id  == RejectId:
                            Plists[L].skipToNextId(RejectId+1,len(con_id_map)+1)
                        else:
                            break
                    continue
                else:
                    fit_cons |= {Plists[K-1].current_entry_id}
                NextId = Plists[K-1].current_entry_id+1
            else:                
                NextId = Plists[K-1].current_entry_id
                
            for L in xrange(K):
                Plists[L].skipToNextId(NextId,len(con_id_map)+1) 
    return fit_cons 
    
def retrievalDocs(cons,con_doc_inverted_index):
    fit_docs = []
    for c in cons:
        fit_docs.extend(con_doc_inverted_index[c])
    return sorted(list(set(fit_docs)))

if __name__ == "__main__":
    con_doc_inverted = defaultdict(list)   
    con_id = defaultdict(int) 
    ass_con_inverted = defaultdict(dict)  
    
    buildTwoLevelInvertedIndex(' age IN 3 AND state IN NY OR state IN CA AND gender IN M','doc1',con_doc_inverted,con_id,ass_con_inverted)    
    buildTwoLevelInvertedIndex(' age IN 3 AND gender IN F OR state NOT CA;NY','doc2',con_doc_inverted,con_id,ass_con_inverted)    
    buildTwoLevelInvertedIndex(' age IN 3 AND gender IN M AND state NOT CA OR state IN CA AND gender IN F','doc3',con_doc_inverted,con_id,ass_con_inverted)    
    buildTwoLevelInvertedIndex(' age IN 3;4  OR state IN CA AND gender IN M','doc4',con_doc_inverted,con_id,ass_con_inverted)    
    buildTwoLevelInvertedIndex(' state NOT CA;NY  OR age IN 3;4','doc5',con_doc_inverted,con_id,ass_con_inverted)    
    buildTwoLevelInvertedIndex(' state NOT CA;NY  OR age IN 3 AND state IN NY OR state IN CA AND gender IN M','doc6',con_doc_inverted,con_id,ass_con_inverted)    
    buildTwoLevelInvertedIndex(' age    IN 3 AND state IN NY OR state IN CA AND gender IN F','doc7',con_doc_inverted,con_id,ass_con_inverted)    
    print "\n$$$$$$$$$$$$$$$$$\n"
    print "con_id:",con_id
    print "\n$$$$$$$$$$$$$$$$$\n"
    print "con_doc_inverted:",con_doc_inverted
    print "\n$$$$$$$$$$$$$$$$$\n"
    print "ass_con_inverted:",ass_con_inverted
    print "\n$$$$$$$$$$$$$$$$$\n"
    
    fit_conjunctions = retrievalConjunctions('age IN 3 AND state IN CA AND gender IN M',con_id,ass_con_inverted)
    print "\n**********\n\nfit_conjunctions:",fit_conjunctions
    fit_docs = retrievalDocs(fit_conjunctions,con_doc_inverted)
    print "\n**********\n\ndocs:",fit_docs,"\n"
    
