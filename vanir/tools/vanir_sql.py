import sys
import vanir
import sqlite3
import vanir.tools

parser = vanir.tools.QubesArgumentParser(
    description='Create new Vanir OS sql.',
    want_app=True,
    want_app_no_instance=True)



	def main(args=None):
    '''Main routine of :program:`vanir-create`.
    :param list args: Optional arguments to override those delivered from \
        command line.
    '''
    vcon = sqlite3.connect('') #storage DB
	v = vcon.cursor()
	
	return 0


if __name__ == '__main__':
    sys.exit(main())