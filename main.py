import os
from StringIO import StringIO
from subprocess import call
from tempfile import *
from shutil import *
from zipfile import *

from xym import *
from bottle import route, run, template, request, static_file

# requests.packages.urllib3.disable_warnings()

pyangcmd = '/usr/local/bin/pyang'
yang_import_dir = '/opt/local/share/yang'

def create_output(url):
	workdir = mkdtemp()
	results = {}

	result = StringIO()

	# Trickery to capture stderr from the xym tools for later use
	stderr_ = sys.stderr
	sys.stderr = result
	extracted_models = xym(source_id = url, dstdir = workdir, srcdir = "", strict = True, debug_level = 0)
	sys.stderr = stderr_
	xym_stderr = result.getvalue()

	for em in extracted_models:
		pyang_stderr, pyang_output = validate_yangfile(em, workdir)
		results[em] = { "pyang_stderr": pyang_stderr, "pyang_output": pyang_output, "xym_stderr": xym_stderr }
	rmtree(workdir)

	return results

def validate_yangfile(infilename, workdir):
	pyang_stderr = pyang_output = ""
	infile = os.path.join(workdir, infilename)
	pyang_outfile = str(os.path.join(workdir, infilename) + '.out')
	pyang_resfile = str(os.path.join(workdir, infilename) + '.res')

	resfp = open(pyang_resfile, 'w+')
	status = call([pyangcmd, '-p', yang_import_dir, '-p', workdir, '--ietf', '-f', 'tree', infile, '-o', pyang_outfile], stderr = resfp)

	if os.path.isfile(pyang_outfile):
		outfp = open(pyang_outfile, 'r')
		pyang_output = str(outfp.read())
	else:
		pass

	resfp.seek(0)

	for line in resfp.readlines():
		pyang_stderr += os.path.basename(line)

	return pyang_stderr, pyang_output

@route('/validator')
def validator():
	return template('main', results = {})


@route('/validator', method="POST")
def upload_file():
	results = {}
	savedfiles = []
	savedir = mkdtemp()

	uploaded_files = request.files.getlist("data")

	for file in uploaded_files:
		name, ext = os.path.splitext(file.filename)

		if ext == ".yang":
			file.save(os.path.join(savedir, file.raw_filename))
			savedfiles.append(file.raw_filename)

		if ext == ".zip":
			zipfilename = os.path.join(savedir, file.filename)
			file.save(zipfilename)
			zf = ZipFile(zipfilename, "r")
			zf.extractall(savedir)
			for filename in zf.namelist():
				# print "Expanded file", filename, "from", zipfilename
				savedfiles.append(filename)

	for file in savedfiles:
		pyang_stderr, pyang_output = validate_yangfile(file, savedir)
		results[file] = { "pyang_stderr": pyang_stderr, "pyang_output": pyang_output }

 	rmtree(savedir)
	return template('main', results = results)

@route('/api/rfc/<rfc>')
def json_validate_rfc(rfc):
	response = []
	url = 'https://tools.ietf.org/rfc/rfc{!s}.txt'.format(rfc)
	results = create_output(url)
	return results

@route('/api/draft/<draft>')
def json_validate_draft(draft):
	response = []
	url = 'http://www.ietf.org/id/{!s}'.format(draft)
	results = create_output(url)
	return results

@route('/rfc', method='GET')
def validate_rfc_param():
	rfc = request.query['number']
	url = 'https://tools.ietf.org/rfc/rfc{!s}.txt'.format(rfc)
	results = create_output(url)
	return template('result', results = results)

@route('/draft', method='GET')
def validate_rfc_param():
	draft = request.query['name']
	url = 'http://www.ietf.org/id/{!s}'.format(draft)
	results = create_output(url)
	return template('result', results = results)

@route('/rfc/<rfc>')
def validate_rfc(rfc):
	response = []
	url = 'https://tools.ietf.org/rfc/rfc{!s}.txt'.format(rfc)
	results = create_output(url)
	return template('result', results = results)

@route('/draft/<draft>')
def validate_draft(draft):
	response = []
	url = 'http://www.ietf.org/id/{!s}'.format(draft)
	results = create_output(url)
	return template('result', results = results)

@route('/static/:path#.+#', name='static')
def static(path):
	return static_file(path, root='static')

run(host='0.0.0.0', port=8080)