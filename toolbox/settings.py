#############################################################################
# Get constants from config files or environment variable
#############################################################################
import os, yaml
# we might not need the _config_file_dir variable; just added it because I encountered a weird bug in JupNB
_config_file_dir = os.path.join(os.path.dirname( os.path.realpath(__file__)))
_config_fname = "configs.yml"
_stage = "dev"

def LoadConfigs( fname, stage = "test"):
    with open(fname, 'r') as ymlfile:
        cfg = yaml.load(ymlfile, Loader = yaml.BaseLoader)

    return cfg[stage]['environment']

def GetVar(strVarName):
    outVar = os.getenv(strVarName)
    if not outVar:
        configs = LoadConfigs(
                    os.path.join(_config_file_dir, _config_fname),
                    _stage)
        outVar = configs[strVarName]
    return outVar

def bool_env(var_name):
	test_val = GetVar(var_name)
	if test_val in ['False', 'false', '0']:
		return False
	return bool(test_val)
