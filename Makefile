.PHONY: proto docs lint typecheck test-unit test-e2e docker-build clean install-hooks release

PROTO_DIR = proto
GEN_DIR = src/pdf_service/generated

proto:
	python -m grpc_tools.protoc \
		-I$(PROTO_DIR) \
		--python_out=$(GEN_DIR) \
		--grpc_python_out=$(GEN_DIR) \
		--pyi_out=$(GEN_DIR) \
		$(PROTO_DIR)/redactr/pdf/v1/pdf_service.proto
	# Fix imports in generated files
	python -c "import glob, re, pathlib; \
		[pathlib.Path(f).write_text(re.sub(r'from redactr\.pdf\.v1', 'from pdf_service.generated.redactr.pdf.v1', pathlib.Path(f).read_text())) \
		for f in glob.glob('$(GEN_DIR)/redactr/pdf/v1/*.py')]"

docs:
	@mkdir -p docs
	python -m grpc_tools.protoc \
		-I$(PROTO_DIR) \
		--plugin=protoc-gen-doc=$$(go env GOPATH)/bin/protoc-gen-doc \
		--doc_out=docs \
		--doc_opt=docs/api.md.tmpl,api.md \
		$(PROTO_DIR)/redactr/pdf/v1/pdf_service.proto

lint:
	ruff check src tests
	ruff format --check src tests

typecheck:
	mypy

test-unit:
	pytest tests/unit -v --cov=src/pdf_service/core

test-e2e:
	docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from test-runner

docker-build:
	docker build -t pdf-core .

clean:
	find $(GEN_DIR) -name "*.py" ! -name "__init__.py" ! -name ".gitkeep" -delete
	find $(GEN_DIR) -name "*.pyi" -delete

install-hooks:
	pre-commit install --hook-type commit-msg

release:
	cz bump
