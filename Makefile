python_version=$(shell python -c "from sys import stdout, version_info as vi; pv='%d.%d' % (vi.major, vi.minor); stdout.write(pv)")
N=ds
M=ansible_ds
V=1.0.0
B=$N-$M-$V.tar.gz

all: clean $B install


clean:
	[ -d ansible_collections ] # insure $PWD is OK.
	/bin/rm -f ansible_collections/$B
	/bin/rm -rf ansible_collections/ds/ansible_ds/tests/output
	find . -name __pycache__ | xargs /bin/rm -rf
	find . -name .pytest_cache | xargs /bin/rm -rf

precommit: unit_test precommit_notest

precommit_notest: clean
	find . -type f | grep -v "^./.git/" | grep -v '/.$$/' | xargs git add

build: $B

$B:
	/bin/rm -f ansible_collections/$B
	cd ansible_collections ; ansible-galaxy collection build -f $N/$M

install:
	/bin/rm -rf $$HOME/.ansible/collections/$N
	cd ansible_collections ; ansible-galaxy collection install $B -f

unit_test: clean $B install
	cd ansible_collections/$N/$M ; ansible-test units -vvvvv --python ${python_version} --local


prereq:
	pip3 install -r requirements.txt

lint:
	pylint --max-line-length=130 '--ignore-long-lines=^\s.*Option.*$$' --method-naming-style=camelCase $$(find . -name '*.py')
	#pylint --max-line-length=130 '--ignore-long-lines=^\s.*Option.*$$' --method-naming-style=camelCase --recursive=y .
	#cd ansible_collections/ds/ansible_ds/tests; py.test --pylint


# Create an ini file that could be customized to run the unit_test
INIFILE=$(HOME)/.389ds-ansible.ini
ini:	$(INIFILE)

$(INIFILE):
	@echo "[/]" >  $(INIFILE)
	@if [ x$(PREFIX) != x ]; then echo PREFIX=$(PREFIX) >> $(INIFILE) ; echo 'LIB389PATH=$${PREFIX}/lib/python3.9/site-packages' >> $(INIFILE) ; fi
	@echo DEBUGGING=1 >> $(INIFILE)
	cat $(INIFILE)

rmini:
	/bin/rm -f $(INIFILE)

