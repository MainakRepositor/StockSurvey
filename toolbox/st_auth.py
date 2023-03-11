import os, sys, functools
import streamlit as st
import streamlit_authenticator as stauth
# streamlit_authenticator docs: https://github.com/mkhorasani/Streamlit-Authenticator
# hased passed generated using stauth.hasher(['your_password']).generate()
USER_DICT = [
	{'name': 'Papa John', 'user':'jho', 'hashed_pass': '$2b$12$qsNIPRIuNJ26mt7Ap4OPh.Paum/y/pclpfAHT22DZ4O2ew1xBq0WC'}
]

#Paths
cwdir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, os.path.join(cwdir, "../"))
from toolbox.st_utils import show_logo

def get_authenticator(user_dict = USER_DICT):
	return stauth.Authenticate(
			names = [u['name'] for u in user_dict],
			usernames = [u['user'] for u in user_dict],
			passwords = [u['hashed_pass'] for u in user_dict],
			cookie_name = 'open_terminal_cookie', key = 'open_terminal',
			cookie_expiry_days = 10
			)

def get_auth_status(debug_mode = False):
	''' return 1 for logged-in, -1 for failed login attempt, and 0 for no login attempt
	'''
	if 'authentication_status' in st.session_state:
		auth_status = st.session_state['authentication_status']
		if debug_mode:
			print(f'auth status set: {auth_status}')

		if auth_status is None:
			return 0
		else:
			return 1 if auth_status else -1
	else:
		if debug_mode:
			print('auth status not in session state')
		return 0

def interactive_login(st_asset, b_show_logo = False,
		str_msg = 'some features are reserved for Beta testers at the moment'
	):
	''' prompt the user to login interactively
	Args:
		st_asset: a streamlit container (can't have columns)
	'''
	if b_show_logo:
		show_logo(st_asset = st_asset, width = 300)
	with st_asset:
		st.info(str_msg)

		# streamlit_authenticator v0.1.4 seems to not init properly
		if get_auth_status() < 1:
			authenticator = get_authenticator()
			name, auth_status, username = authenticator.login('Login', 'main')

			if auth_status == True:
				st.success(f'Welcome Back {st.session_state["name"]}!')
			elif auth_status == False:
				st.error(f'login attempt failed!')
				if st.button('Try Again'):
					st.session_state['authentication_status'] == None
					st.session_state['name'] == None
		else:
			st.success(f'Welcome Back {st.session_state["name"]}!')

def run_if_auth(run_func):
	def wrapper(*args, **kwargs):
		auth_status = get_auth_status()
		if auth_status ==1:
			return run_func(*args, **kwargs)
		else:
			st.warning('beta feature disabled. to enable, please login.')
	return wrapper

def auth_before_run(run_func):
	def wrapper(*args, **kwargs):
		auth_status = get_auth_status()
		if auth_status ==1:
			return run_func(*args, **kwargs)
		else:
			st_asset = st.container()
			st_asset.warning(f'please rerun app (press r) after login')
			return interactive_login(st_asset = st_asset, b_show_logo = False)
	return wrapper

# def auth_before_run(run_func=None, *, st_asset = st.container()):
# 	#TODO: doing default args for decorator function is tricky
# 	#see: https://realpython.com/primer-on-python-decorators/#both-please-but-never-mind-the-bread
#
# 	def decorator_auth(func):
# 		@functools.wraps(func)
# 		def wrapper(*args, **kwargs):
# 			auth_status = get_auth_status()
# 			if auth_status==0:
# 				with st_asset:
# 					st.write(f'please rerun app after logging in (press r)')
# 					return interactive_login(st_asset = st_asset, b_show_logo = False)
# 			elif auth_status == 1:
# 				return func(*args, **kwargs)
# 			else:
# 				with st_asset:
# 					st.write(str_msg)
# 		return wrapper
#
# 	if run_func is None:
# 		return decorator_auth
# 	else:
# 		return decorator_auth(run_func)
