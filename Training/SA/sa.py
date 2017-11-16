import tensorflow as tf
import numpy as np
import read as r
from functools import reduce

transe_size = 100
dev = 0.01
lstm_size = 100
hidden_layer = 50
batch_size = 1000
train_num = 10000
check_num = 1000
prob = 0.5


'''constructing the NN'''
entity_in = tf.placeholder(tf.float32, [None, r.word_size])

left_in = [ tf.placeholder(tf.float32, [None, r.word_size]) for _ in range(r.window) ] #from middle to side
right_in = [ tf.placeholder(tf.float32, [None, r.word_size]) for _ in range(r.window) ]#from middle to side
left_in_rev = [ left_in[r.window-1-i] for i in range(r.window) ]  #from side to middle
right_in_rev = [ right_in[r.window-1-i] for i in range(r.window) ]#from side to middle


left_middle_lstm = tf.nn.rnn_cell.LSTMCell(lstm_size)
right_middle_lstm = tf.nn.rnn_cell.LSTMCell(lstm_size)
left_side_lstm = tf.nn.rnn_cell.LSTMCell(lstm_size)
right_side_lstm = tf.nn.rnn_cell.LSTMCell(lstm_size)

with tf.variable_scope('root'):
	
	with tf.variable_scope('lstm'):
		left_out_rev, state0 = tf.nn.rnn(left_middle_lstm, left_in_rev, dtype=tf.float32)   #from side to middle
	
	with tf.variable_scope('lstm', reuse=True):
		right_out_rev, state1 = tf.nn.rnn(right_middle_lstm, right_in_rev, dtype=tf.float32)#from side to middle
		left_out, state2 = tf.nn.rnn(left_side_lstm, left_in, dtype=tf.float32)   #from middle to side
		right_out, state3 = tf.nn.rnn(right_side_lstm, right_in, dtype=tf.float32)#from middle to side
		
'''
assume, originally the sequence should be [0,1,2,3]#middle to side
left_in = [3,2,1,0]#side to middle
left_in_rev = [0,1,2,3]#middle to side
after lstm processing
left_out = [3,2,1,0]#side to middle
left_out_rev = [0,1,2,3]#middle to side
left_out_rev2 = [3,2,1,0]#so that it is conpatible with left_out
'''

#attention layer

left_att_in = [ tf.concat(1, [left_out[i], left_out_rev[r.window-1-i]]) for i in range(r.window) ]   #left then right
right_att_in = [ tf.concat(1, [right_out[i], right_out_rev[r.window-1-i]]) for i in range(r.window) ]#right then left
#both side then middle

W1 = tf.Variable(tf.random_normal([lstm_size*2, hidden_layer], stddev=dev))
W2 = tf.Variable(tf.random_normal([hidden_layer, 1], stddev=dev))

left_att = [ tf.exp(tf.matmul(tf.tanh(tf.matmul(left_att_in[i], W1)), W2)) for i in range(r.window) ]
right_att = [ tf.exp(tf.matmul(tf.tanh(tf.matmul(right_att_in[i], W1)), W2)) for i in range(r.window) ]

left_weighted = reduce(tf.add, [ left_att_in[i]*left_att[i] for i in range(r.window) ])
right_weighted = reduce(tf.add, [ right_att_in[i]*right_att[i] for i in range(r.window) ])

left_all = reduce(tf.add, [ left_att[i] for i in range(r.window) ])
right_all = reduce(tf.add, [ right_att[i] for i in range(r.window) ])

context_in = tf.concat(1, [left_weighted/left_all, right_weighted/right_all])

kprob = tf.placeholder(tf.float32)

entity_drop = tf.nn.dropout(entity_in, kprob)

x = tf.concat(1, [entity_drop, context_in])


W = tf.Variable(tf.random_normal([r.word_size+lstm_size*4, r.type_size], stddev=dev))
t = tf.nn.sigmoid(tf.matmul(x, W))
t_ = tf.placeholder(tf.float32, [None, r.type_size])


loss = -tf.reduce_sum(t_*tf.log(t+1e-10)) - tf.reduce_sum((1-t_)*tf.log(1-t+1e-10))
train = tf.train.AdamOptimizer(0.005).minimize(loss)

saver = tf.train.Saver(max_to_keep=100)

sess = tf.Session(config=tf.ConfigProto(intra_op_parallelism_threads=8))
initializer = tf.global_variables_initializer()



'''the function of obtaining the result'''
def guess(y, y_, sess, fd, th=0.5):
	showy = sess.run(y, feed_dict=fd)
	showy_ = fd[y_]
	h = showy > th
	
	for i in range(np.shape(h)[0]):
		if np.sum(h[i, :])==0:
			h[i, np.argmax(showy[i, :])] = 1
			
	true_pos = np.sum(np.logical_and(h, showy_))
	false_pos = np.sum(h)
	true_neg = np.sum(showy_)
	precision = true_pos / float(false_pos)
	recall = true_pos / true_neg
	return (precision, recall, (2*precision*recall)/(precision+recall), true_pos, false_pos, true_neg)


'''the function of constructing a feed_dict from dataset'''
def fdict(now, size, interval, _entity, _context, _label):
	fd = {}
	new_size = int(size/interval)
	
	ent = np.zeros([new_size, r.word_size])
	lab = np.zeros([new_size, r.type_size])
	for i in range(new_size):
		vec = np.zeros([r.word_size])
		l = len(_entity[now+i*interval])
		for j in range(l):
			vec += r.dic( _entity[now+i*interval][j] )
		ent[i] = vec/l
		lab[i] = _label[now+i*interval]
	fd[entity_in] = ent
	fd[t_] = lab
	
	for j in range(r.window):# window3 j0 jj2; j1 jj1; j2 jj0;
		left_con = np.zeros([new_size, r.word_size])
		right_con = np.zeros([new_size, r.word_size])
		for i in range(new_size):
			left_con[i, :] = r.dic( _context[now+i*interval][2*j] )
			right_con[i, :] = r.dic( _context[now+i*interval][2*j+1] )
		fd[left_in[j]] = left_con
		fd[right_in[j]] = right_con
		
	return fd


'''read in data'''

train_entity = np.load('train_entity.npy')
train_context = np.load('train_context.npy')
train_label = np.load('train_label.npy')
train_fbid = np.load('train_fbid.npy')

valid_entity = np.load('valid_entity.npy')
valid_context = np.load('valid_context.npy')
valid_label = np.load('valid_label.npy')
valid_fbid = np.load('/valid_fbid.npy')

test_entity = np.load('test_entity.npy')
test_context = np.load('test_context.npy')
test_label = np.load('test_label.npy')
test_fbid = np.load('test_fbid.npy')



'''train and test'''
fdw = fdict(0, r.train_size, 1000, train_entity, train_context, train_label)
fdw[kprob] = prob



def test(n, version):
	true_pos = 0
	false_pos = 0
	true_neg = 0

	for i in range(int(r.test_size/batch_size)):
		if version=='test':
			fdt = fdict(i*batch_size, batch_size, 1, test_entity, test_context, test_label)
		else:
			fdt = fdict(i*batch_size, batch_size, 1, valid_entity, valid_context, valid_label)
		fdt[kprob] = 1.0
		result = guess(t, t_, sess, fdt)
		
		true_pos += result[3]
		false_pos += result[4]
		true_neg += result[5]


	precision = true_pos / float(false_pos)
	recall = true_pos / true_neg
	print(version)
	print('%d %f %f %f' %(n, precision, recall, (precision*recall*2)/(precision+recall)))


print('\nStart training')
sess.run(initializer)
Now = 0

for i in range(train_num):
	fd = fdict(Now, batch_size, 1, train_entity, train_context, train_label)
	fd[kprob] = prob
	Now += batch_size
	if Now>=r.train_size:
		Now = 0
	
	sess.run(train, feed_dict=fd)
	
	
	if i%check_num==0:
		result = guess(t, t_, sess, fd)
		print('%d %f %f %f\t%f' %(i, result[0], result[1], result[2], sess.run(loss, feed_dict=fd)))
		result = guess(t, t_, sess, fdw)
		print('%d %f %f %f\t%f' %(i, result[0], result[1], result[2], sess.run(loss, feed_dict=fdw)))
		test(i, 'valid')
		test(i, 'test')
		print('')

		saver.save(sess, 'para/model', global_step=i)
