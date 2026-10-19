import json,os,sys
with open(os.environ['AMIND_PREFIX_LOG'],'a') as f:f.write(json.dumps(sys.argv[1:])+'\n')
os.execv(sys.argv[1],sys.argv[1:])
