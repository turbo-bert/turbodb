import sys
import argparse
import os
import os.path
import json


def compile_fac(out_filename, uml_filename):
    python_block_indent = "    "
    lines = []
    with open(uml_filename, "r") as f:
        lines = [l.strip() for l in f.read().split("\n") if len(l.strip()) > 0]
    lines2 = [l for l in lines if not l.startswith("'")]
    lines = lines2

    entities = {}

    init_objects={}

    # get entity names
    for line in lines:
        if line.startswith("#"):
            continue
        if line.find("object ") == 0:
            entity_name = line.split()[1]
            entities[entity_name] = {}
            init_objects[entity_name] = []

    # get members
    for line in lines:
        if line.startswith("#"):
            continue
        if line.find(":") > -1 and line.split(":")[0].find("-") < 0:
            if line.split()[0] in entities:
                entity_name = line.split()[0]
                col = line.split(":")[1].split("(")[0].strip()
                coltype = line.split("(")[1].split(")")[0].strip()
                # print("object(%s) member(%s) type(%s)" % (entity_name, col, coltype))
                entities[entity_name][col] = coltype
    relationships = {}

    ref_by = {}
    entity_refs = {}

    # get foreign key constraints
    for line in lines:# 
        if line.startswith("#"):
            continue
        if line.startswith("'"):
            continue
        if line.find(" <- ") > -1:
            line_tmp = line.replace(" ", "")
            line_tmp = line_tmp.replace("<-", ":")
            line_tmp = line_tmp.replace('"', "")
            (fk_targettable, fk_sourcetable, fk_member) = line_tmp.split(":")
            if entities[fk_sourcetable][fk_member] == "FK":
                print("Found valid FK")

                if not fk_sourcetable in entity_refs.keys():
                    entity_refs[fk_sourcetable] = []
                entity_refs[fk_sourcetable].append(fk_member)
                #prep_sig.append(fk_member)

                entities[fk_sourcetable][fk_member] = "Integer, ForeignKey('%s.%s_id')" % (
                    fk_targettable, fk_targettable)
                if fk_sourcetable not in relationships:
                    relationships[fk_sourcetable] = {}
                if fk_targettable not in relationships:
                    relationships[fk_targettable] = {}
                relationships[fk_sourcetable][fk_targettable] = "%s = relationship('%s', back_populates='%ss')" % (
                    fk_targettable, fk_targettable, fk_sourcetable)
                #if not fk_sourcetable in init_objects:
                #    init_objects[fk_sourcetable] = []
                init_objects[fk_sourcetable].append(fk_targettable)
                #print(fk_sourcetable)
                #if fk_sourcetable not in ref_by.keys():
                #    ref_by[fk_sourcetable] = []
                #ref_by[fk_sourcetable].append(fk_targettable)
                ##print(fk_targettable)
                relationships[fk_targettable][fk_sourcetable] = "%ss = relationship('%s', back_populates='%s')" % (
                    fk_sourcetable, fk_sourcetable, fk_targettable)
            else:
                print("ERROR (%s.%s refs %s)" % (fk_sourcetable, fk_member, fk_targettable))

    print(ref_by)
    outfile = open(out_filename, "w")
    outfile.write("""# DO NOT EDIT THIS BY HAND
# Supported Column Types: PK, FK, FLOAT, INT, DATETIME, TEXT, TEXT<X>

# ----- SOURCE START -----
""")
    for source_line in lines:
        outfile.write("#%s\n" % source_line)
    outfile.write('# ----- SOURCE END -----\n\n')
    outfile.write('# ----- GENERATED CODE STARTS HERE -----\n\n')
    outfile.write("from sqlalchemy.ext.declarative import declarative_base\n")
    outfile.write("from sqlalchemy import Column, Integer, String, Numeric, DateTime, Date, Float\n")
    outfile.write("from sqlalchemy import ForeignKey\n")
    outfile.write("from sqlalchemy.sql import func\n")
    outfile.write("from sqlalchemy.orm import relationship\n")
    outfile.write("\n")
    outfile.write("Base = declarative_base()\n")

    import re

    digits_only = re.compile(r'[^\d]+')

    for entity_name in entities:
        default_init_prototype = []
        all_prototype = []
        outfile.write("\n")
        outfile.write("class %s(Base):\n" % entity_name)
        outfile.write("%s__tablename__ = '%s'\n" % (python_block_indent, entity_name))
        for col in entities[entity_name]:
            coltype = entities[entity_name][col]
            if coltype == "PK":
                coltype = "Integer, primary_key=True"
                all_prototype.append(col)
            elif coltype == "NUMERIC":
                coltype = "Numeric(10,2)"
                default_init_prototype.append(col)
                all_prototype.append(col)
            elif coltype == "FLOAT":
                coltype = "Float"
                default_init_prototype.append(col)
                all_prototype.append(col)
            elif coltype == "INT":
                coltype = "Integer"
                default_init_prototype.append(col)
                all_prototype.append(col)
            elif coltype == "DATETIME":
                coltype = "DateTime"
                default_init_prototype.append(col)
                all_prototype.append(col)
            elif coltype.find("TEXT") == 0:
                default_init_prototype.append(col)
                all_prototype.append(col)
                length = 256
                length_tmp = digits_only.sub('', coltype)
                if len(length_tmp) > 0:
                    length = int(length_tmp)
                coltype = "String(%d)" % length
            elif coltype.find("Integer,") == 0:
                pass
            elif coltype == "FK":
                print("ERROR unresolved FK (%s.%s)" % (entity_name, col))
            else:
                print("ERROR coltype unknown (%s)" % coltype)
            outfile.write("%s%s = Column(%s)\n" % (python_block_indent, col, coltype))

        if entity_name in relationships:
            # we have foreign keys, let's build relationships
            for fk_targettable in relationships[entity_name]:
                #all_prototype.append(fk_targettable + "_id")
                outfile.write("%s%s\n" % (python_block_indent, relationships[entity_name][fk_targettable]))

        outfile.write("\n")
        fks_without_back_populates = init_objects[entity_name] #[ x[0:-3] for x in prep_sig[1:]]
        print("*"*80)
        print(entity_name + "---" + repr(fks_without_back_populates))
        print("*"*80)

        sigs = all_prototype[1:] + fks_without_back_populates
        sig_none = [ x + "=None" for x in sigs]
        sig_id = [ x + "="+x for x in sigs]
        outfile.write("    def create(%s):\n" % (", ".join(sig_none)))
        outfile.write("        return %s(%s)\n" % (entity_name, (", ".join(sig_id))))
        outfile.write("\n")

        outfile.write("%sdef __repr__(self):\n" % (python_block_indent * 1))
        if entity_name in entity_refs.keys():
            all_prototype += entity_refs[entity_name]
        vs = ["%s={self.%s}" % (f, f) for f in all_prototype]
        outfile.write("%sreturn f'<%s %s>'\n" % (python_block_indent * 2, entity_name, ', '.join(vs)))

        outfile.write("\n")
        outfile.write("%sdef to_dict(self):\n" % (python_block_indent * 1))
        outfile.write(
            "%sreturn {c.name: getattr(self, c.name) for c in self.__table__.columns}\n" % (python_block_indent * 2))
        outfile.write("\n")
        outfile.write("def %s_from_dict(jsonString):\n" % (entity_name))
        outfile.write("%simport json\n" % (python_block_indent * 1))
        outfile.write("%so = json.loads(jsonString)\n" % (python_block_indent * 1))
        param_init = []
        for col in entities[entity_name]:
            outfile.write("%sif '%s' not in o.keys():\n" % (python_block_indent * 1, col))
            outfile.write("%so['%s'] = None\n" % (python_block_indent * 2, col))
        for col in entities[entity_name]:
            param_init.append("%s=o['%s']" % (col, col))

        outfile.write("%sreturn %s(%s)\n" % (python_block_indent * 1, entity_name, ", ".join(param_init)))
        outfile.write("\n")
        outfile.write("def mk_atom_%s(%s) -> %s:\n" % (entity_name, ', '.join(default_init_prototype), entity_name))
        assigns = ["%s=%s" % (f, f) for f in default_init_prototype]
        outfile.write("%sreturn %s(%s)\n" % (python_block_indent * 1, entity_name, ', '.join(assigns)))
        # \n" % ())
        outfile.write("\n")

    outfile.write("\n")
    outfile.write("\n")
    outfile.write("from sqlalchemy import create_engine\n")
    outfile.write("from sqlalchemy.orm import sessionmaker\n")
    outfile.write("from sqlalchemy.orm.session import Session as session_type\n")
    outfile.write("\n")
    outfile.write("engine = None\n")
    outfile.write("Session = None\n")
    outfile.write("session: session_type\n")
    outfile.write("session = None\n")
    outfile.write("uri_ = None\n")
    outfile.write("\n")
    outfile.write("def uri(uri=None):\n")
    outfile.write("%s\n" % python_block_indent)
    outfile.write("%sglobal uri_\n" % python_block_indent)
    outfile.write("%suri_ = uri\n" % python_block_indent)
    outfile.write("\n")
    outfile.write("def file(filename='db.sql'):\n")
    outfile.write("%s\n" % python_block_indent)
    outfile.write("%sglobal uri_\n" % python_block_indent)
    outfile.write("%suri_ = 'sqlite:///%%s' %% filename\n" % python_block_indent)
    outfile.write("\n")
    outfile.write("def jkl():\n")
    outfile.write("%swith open('jkl.uri', 'r') as f:\n" % python_block_indent)
    outfile.write("%suri(f.read().split('\\n')[0].strip())\n" % (python_block_indent*2))
    outfile.write("%sload()\n" % python_block_indent)
    outfile.write("\n")
    outfile.write("def load():\n")
    outfile.write("%s\n" % python_block_indent)
    outfile.write("%sglobal engine\n" % python_block_indent)
    outfile.write("%sglobal Session\n" % python_block_indent)
    outfile.write("%sglobal session\n" % python_block_indent)
    outfile.write("%sglobal Base\n" % python_block_indent)
    outfile.write("%s\n" % python_block_indent)
    outfile.write("%sif uri_ == None:\n" % python_block_indent)
    outfile.write("%sengine = create_engine('sqlite:///:memory:', echo=True)\n" % (python_block_indent * 2))
    outfile.write("%selse:\n" % python_block_indent)
    outfile.write("%sengine = create_engine(uri_)\n" % (python_block_indent * 2))
    outfile.write("%sSession = sessionmaker(bind=engine)\n" % python_block_indent)
    outfile.write("%ssession = Session()\n" % python_block_indent)
    outfile.write("\n")
    outfile.write("def format():\n")

    outfile.write('%sif uri_.find("sqlite:///") == 0:\n' % (python_block_indent))
    outfile.write('%sfilename = uri_[len("sqlite:///"):]\n' % (python_block_indent * 2))
    outfile.write('%simport os\n' % (python_block_indent * 2))
    outfile.write('%simport os.path\n' % (python_block_indent * 2))
    outfile.write('%sif os.path.isfile(filename):\n' % (python_block_indent * 2))
    outfile.write('%sos.remove(filename)\n' % (python_block_indent * 3))
    outfile.write('%sBase.metadata.create_all(engine)\n' % (python_block_indent * 2))

    outfile.write('%sif uri_.find("mysql:") == 0:\n' % python_block_indent)
    outfile.write('%sengine.execute("set FOREIGN_KEY_CHECKS=0;")\n' % (python_block_indent * 2))
    outfile.write('%sBase.metadata.drop_all(engine)\n' % (python_block_indent * 2))
    outfile.write('%sengine.execute("set FOREIGN_KEY_CHECKS=1;")\n' % (python_block_indent * 2))
    outfile.write('%sBase.metadata.create_all(engine)\n' % (python_block_indent * 2))

    outfile.write('%sif uri_.find("postgresql+pg8000:") == 0:\n' % python_block_indent)
    outfile.write('%sBase.metadata.drop_all(engine)\n' % (python_block_indent * 2))
    outfile.write('%sBase.metadata.create_all(engine)\n' % (python_block_indent * 2))

    outfile.write("\n")

    outfile.write("# copy pase import code\n")
    # for e in entities:
    #    outfile.write("#from %s import %s\n" % (libname, e))

    outfile.write("\n")

    outfile.flush()
    outfile.close()
    print("="*80)
    print("Debug")
    print("="*80)
    print("entity_refs")
    print(json.dumps(entity_refs, indent=4))
    print("entities")
    print(json.dumps(entities, indent=4))
    print("relationships")
    print(json.dumps(relationships, indent=4))
    print("ref_by")
    print(json.dumps(ref_by, indent=4))

cmd = None

if len(sys.argv) > 1:
    cmd = sys.argv[1]

if cmd is None:
    print("Try 'help'.")
    sys.exit(0)

if cmd == 'compile':
    uml_filename = sys.argv[2]
    out_filename = 'db.py'
    print(f"will compile {uml_filename} into {out_filename}")
    compile_fac(out_filename=out_filename, uml_filename=uml_filename)
    sys.exit(0)


# generate a main cli example file
if cmd == 'main-cli':
    db_filename = 'db.py'
    main_filename = 'main.py'

    with open(db_filename, 'r') as f:
        source_lines = f.read().split('\n')

    entity_names = [ x.split(' ')[1].split('(')[0] for x in source_lines if x.find('Base') >= 0 and x.find('class') >= 0]

    src = """import db


db.file(filename='db.sql')
db.load()
db.format()



"""
    import subprocess
    entities = subprocess.check_output('cat db.py | grep ^class | grep Base | cut -d " " -f 2 | cut -d "(" -f 1', shell=True, universal_newlines=True).strip().split("\n")


    for entity_name in entities:
        constructor_parameters = subprocess.check_output('cat db.py | grep "%s %s_id" | head -1' % (entity_name, entity_name), shell=True, universal_newlines=True).strip().split("}, ")[1:]
        constructor_parameters = ", ".join([ x.split("=")[0] + "=None" for x in constructor_parameters])

        src += entity_name.lower() + ' = db.'+entity_name+'(%s)\n' % constructor_parameters
        src += 'db.session.add(' + entity_name.lower() + ')\n'
        src += 'db.session.commit()\n'
        src += '\n'



    with open (main_filename, 'w') as f:
        f.write(src)
    with open ("Makefile", 'w') as f:
        f.write("default:\n")
        f.write("\t${HOME}/bin/ob py -u main.py\n")
    sys.exit(0)

# convert light-uml to uml for plantuml and parsing
if cmd == 'uml':
    uml_filename = sys.argv[2]
    out_filename = uml_filename.replace('.luml', '.uml')

    with open(uml_filename) as f:
        lines = [l.strip() for l in f.read().split('\n') if len(l.strip()) > 0 and not l.strip().startswith('#')]

    i: int
    i = 0
    cols = []
    tables = {}
    current_table: str
    current_table = None
    while i < len(lines):
        if lines[i].find(' ') < 0:
            # table name
            current_table = lines[i]
            tables[current_table] = []
        else:
            tables[current_table].append(lines[i].split(' ')[0:2])
        i += 1

    fks = []
    ow=0
    with open(out_filename, 'w') as f:
        for table in tables.keys():
            if ow>0:
                f.write('\n')
            f.write('object %s\n' % table)
            ow+=1
            f.write('%s : %s (PK)\n' % (table, table+'_id'))
            for cols in tables[table]:
                if cols[0] == 'FK':
                    f.write('%s : %s_id (%s)\n' % (table, cols[1], cols[0]))
                    fks.append([table, cols[1]])
                else:
                    f.write('%s : %s (%s)\n' % (table, cols[1], cols[0]))
        f.write('\n')
        for con in fks:
            f.write('%s <- %s: " %s_id "\n' % (con[1], con[0], con[1]))
    sys.exit(0)
