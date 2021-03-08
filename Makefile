.PHONY: doc, runGittk, runDemo, build, testdeploy, deploy

.venv:
	python3 -m venv .venv
	. .venv/bin/activate
	pip3 install --upgrade pdoc3
	pip3 install --upgrade GitPython
	pip3 install --upgrade build
	pip3 install --upgrade twine

doc: .venv
	. .venv/bin/activate
	rm -rf docs/html
	pdoc --html TermTk -o docs/html

runGittk: .venv
	. .venv/bin/activate
	demo/gittk.py -f

runDemo: .venv
	. .venv/bin/activate
	demo/demo.py -f

build: .venv
	. .venv/bin/activate
	rm -rf dist
	python3 -m build

deployDoc:
	git checkout gh-pages
	cp -a docs/html/TermTk/*
	find index.html TTk* libbpytop -name "*.html" | xargs git add
	git commit -m "Doc Updated"
	git push origin gh-pages
	git checkout main

testDeploy: .venv
	. .venv/bin/activate
	python3 -m twine upload --repository testpypi dist/* --verbose

deploy: .venv
	. .venv/bin/activate
	python3 -m twine upload dist/*
