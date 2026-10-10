XARGS := xargs -0 $(shell test $$(uname) = Linux && echo -r)
GREP_T_FLAG := $(shell test $$(uname) = Linux && echo -T)

all:
	@echo "\nThere is no default Makefile target right now. Try:\n"
	@echo "make run - run the local development version of Mu."
	@echo "make clean - reset the project and remove auto-generated assets."
	@echo "make lint - run the ruff code checker."
	@echo "make test - run the test suite."
	@echo "make coverage - view a report on test coverage."
	@echo "make format - check code formatting with ruff."
	@echo "make tidy - reformat code with the 'ruff' formatter."
	@echo "make check - run all the checkers and tests."
	@echo "make dist - make a dist/wheel for the project."
	@echo "make publish-test - publish the project to PyPI test instance."
	@echo "make publish-live - publish the project to PyPI production."
	@echo "make docs - build the documentation with MkDocs."
	@echo "make docs-serve - serve the documentation locally with live reload."
	@echo "make translate_begin LANG=xx_XX - create/update a mu.po file for translation."
	@echo "make translate_done LANG=xx_XX - compile translation strings in mu.po to mu.mo file."
	@echo "make translate_test LANG=xx_XX - run translate_done and launch Mu in the given LANG."
	@echo "make win64 - build a 64bit Windows MSI installer (Briefcase)."
	@echo "make macos - build a macOS native application (Briefcase)."
	@echo "make linux - build a Linux AppImage (Briefcase)."
	@echo "make video - create an mp4 video representing code commits.\n"

clean:
	rm -rf build
	rm -rf dist
	rm -rf .coverage
	rm -rf .eggs
	rm -rf *.egg-info
	rm -rf site
	rm -rf .pytest_cache
	rm -rf lib
	rm -rf *.mp4
	rm -rf .git/avatar/*
	find . \( -name '*.py[co]' -o -name dropin.cache \) -delete
	find . \( -name '*.bak' -o -name dropin.cache \) -delete
	find . \( -name '*.tgz' -o -name dropin.cache \) -delete
	find . | grep -E "(__pycache__)" | xargs rm -rf
	rm -f ./mu/locale/messages.pot
	rm -f ./mu/wheels/*.zip

run: clean
ifeq ($(VIRTUAL_ENV),)
	@echo "\n\nCannot run Mu. Your Python virtualenv is not activated."
else
	python run.py
endif

lint:
	@python make.py lint

test: clean
	export LANG=en_GB.utf8
	pytest -v --random-order

coverage: clean
	export LANG=en_GB.utf8
	pytest -v --random-order --cov-config pyproject.toml --cov-report term-missing --cov=mu tests/

tidy:
	python make.py tidy

format:
	python make.py format

check: clean format lint coverage

dist: check
	@echo "\nChecks pass, good to package..."
	python -m build

publish-test: dist
	@echo "\nPackaging complete... Uploading to PyPi..."
	twine upload -r test --sign dist/*

publish-live: dist
	@echo "\nPackaging complete... Uploading to PyPi..."
	twine upload --sign dist/*

docs:
	@python make.py docs
	@echo "\nDocumentation can be found here:"
	@echo file://`pwd`/site/index.html
	@echo "\n"

docs-serve:
	@python -m mkdocs serve

translate_begin:
	@python make.py translate_begin LANG=$(LANG)

translate_done:
	@python make.py translate_done LANG=$(LANG)

translate_test:
	@python make.py translate_test LANG=$(LANG)

win64: check
	@echo "\nBuilding 64bit Windows MSI installer (Briefcase)."
	python make.py win64

macos: check
	@echo "\nBuilding macOS native application (Briefcase)."
	python make.py macos

linux: check
	@echo "\nBuilding Linux AppImage (Briefcase)."
	python make.py linux

video: clean
	@echo "\nFetching contributor avatars."
	python utils/avatar.py
	@echo "\nMaking video of source commits."
	gource --user-image-dir .git/avatar/ --title "The Making of Mu" --logo docs/icon_small.png --font-size 24 --file-idle-time 0 --key -1280x720 -s 0.1 --auto-skip-seconds .1 --multi-sampling --stop-at-end --hide mouse,progress --output-ppm-stream - --output-framerate 30 | ffmpeg -y -r 30 -f image2pipe -vcodec ppm -i - -b 65536K movie.mp4
