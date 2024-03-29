python_version=$(shell python -c "from sys import stdout, version_info as vi; pv='%d.%d' % (vi.major, vi.minor); stdout.write(pv)")
N=ds389
M=ansible_ds
V=1.0.0
B=$N-$M-$V.tar.gz
SRCBASE=ansible_collections/$N/$M

all: clean $B install


clean:
	[ -d ansible_collections ] # insure $PWD is OK.
	/bin/rm -f ansible_collections/$B $M.tgz
	/bin/rm -rf ansible_collections/ds389/ansible_ds/tests/output
	find . -name __pycache__ | xargs /bin/rm -rf
	find . -name .pytest_cache | xargs /bin/rm -rf
	/bin/rm -f pytest.out

precommit: unit_test precommit_notest

precommit_notest: clean
	find . -type f | grep -v "^./.git/" | grep -v '/.$$/' | xargs git add

build: $B

$B: gensrc
	/bin/rm -f ansible_collections/$B
	cd ansible_collections ; ansible-galaxy collection build -f $N/$M
	cp -f ansible_collections/$B $M.tgz

install:
	/bin/rm -rf $$HOME/.ansible/collections/$N
	cd ansible_collections ; ansible-galaxy collection install $B -f

unit_test: clean $B install
	# ansible-test seems to do its own test collection and ignore yml test so use directly pytest
	#cd ansible_collections/$N/$M ; ansible-test units -vvvvv --python ${python_version} --local
	pytest -rap -vvvvv ansible_collections/$N/$M/tests 2>&1 | tee pytest.out

prereq:
	pip3 install -r requirements.txt

lint:
    # Lets exclude the plugins code until we have done a code cleanup
	pylint -r y .

github_pylint: lint

github_anlint: install
	ANSIBLE_COLLECTIONS_PATH=$(HOME)/.ansible/collections ansible-lint

github_utest:
	pytest-3 -rap -vvvvv ansible_collections/$N/$M/tests


gensrc: $(SRCBASE)/plugins/doc_fragments/ds389_server_doc.py $(SRCBASE)/plugins/module_utils/ds389_entities_options.py

$(SRCBASE)/plugins/doc_fragments/ds389_server_doc.py: utils/gendoc.py $(SRCBASE)/plugins/module_utils/ds389_entities.py
	python ./utils/gendoc.py doc > $(SRCBASE)/plugins/doc_fragments/ds389_server_doc.py.tmp
	mv -f $(SRCBASE)/plugins/doc_fragments/ds389_server_doc.py.tmp $(SRCBASE)/plugins/doc_fragments/ds389_server_doc.py

$(SRCBASE)/plugins/module_utils/ds389_entities_options.py: utils/gendoc.py $(SRCBASE)/plugins/module_utils/ds389_entities.py
	python ./utils/gendoc.py spec > $(SRCBASE)/plugins/module_utils/ds389_entities_options.py.tmp
	mv -f $(SRCBASE)/plugins/module_utils/ds389_entities_options.py.tmp $(SRCBASE)/plugins/module_utils/ds389_entities_options.py

# Create an ini file that could be customized to run the unit_test
INIFILE=$(HOME)/.ds389-ansible.ini
ini:	$(INIFILE)

$(INIFILE):
	@echo "[/]" >  $(INIFILE)
	@if [ x$(PREFIX) != x ]; then echo PREFIX=$(PREFIX) >> $(INIFILE) ; echo 'LIB389PATH=$${PREFIX}/lib/python$(python_version)/site-packages' >> $(INIFILE) ; fi
	@echo DEBUGGING=1 >> $(INIFILE)
	cat $(INIFILE)

rmini:
	/bin/rm -f $(INIFILE)

