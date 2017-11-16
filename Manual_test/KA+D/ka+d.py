import structure as s
import read as r
import numpy as np
import sys

threshold = 0.55
batch_size = 100
test_size = 100

'''read in data'''
embedding = np.load('embedding.npy')


test_entity = np.load('manual_entity.npy')
test_context = np.load('manual_context.npy')
test_label = np.load('manual_label.npy')
test_fbid = np.load('manual_fbid.npy')
linktest = np.load('linkmanual.npy')



def test(version):
	true_pos = 0
	false_pos = 0
	true_neg = 0	
	strict = 0
	lma_p = 0
	lma_r = 0
	effect = 0
	#organization 0 person 13 location 54

	
	for i in range(int(test_size/batch_size)):		

		if version=='all':
			table = np.ones([batch_size])
		elif version=='succ':
			table = linktest[i*batch_size : (i+1)*batch_size]
		elif version=='miss':
			table = np.ones([batch_size]) - linktest[i*batch_size : (i+1)*batch_size]		
		else:
			table = np.zeros([batch_size])
		
		fdt = s.tfdict(i*batch_size, batch_size, 1, test_entity, test_context, test_label, embedding)
		t = -1
		if version=='person':
			t = 13
		elif version=='organization':
			t = 0
		elif version=='location':
			t = 54
		if t>-1:			
			for j in range(batch_size):			
				if test_label[i*batch_size+j][t]==1:
					table[j] = 1
					
		fdt[s.kprob] = 1.0
		fdt[s.sh] = threshold
		
		
		result = s.guess(s.t, s.t_, s.sess, fdt, table)
		
		strict += result[0]
		lma_p += result[1]
		lma_r += result[2]
		true_pos += result[3]
		false_pos += result[4]
		true_neg += result[5]
		effect += result[6]
		
					

	precision = true_pos / false_pos
	recall = true_pos / true_neg
	print(version)
	print('strict: %f' %(strict/effect))
	print('loose-macro: %f %f %f'   %(lma_p/effect, lma_r/effect, (2*lma_p*lma_r)/(lma_p+lma_r)/effect))
	print('loose-micro: %f %f %f\n\n' %(precision, recall, (precision*recall*2)/(precision+recall)))

'''testing'''

def onehot(h):
	print(h)
	for j in range(r.type_size):
		if h[j]:
			print(r.n2t[j])
	print('')

s.sess.run(s.initializer)
s.new_saver.restore(s.sess, '../../Parameter/para_ka+d/model-5600')

print('Start testing')


	
test('all')
test('succ')
test('miss')
test('person')
test('organization')
test('location')