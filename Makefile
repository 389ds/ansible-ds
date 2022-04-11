
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

unit_test:
	cd ansible_collections/$N/$M ; ansible-test units -vvvvv --python 3.9 --local


