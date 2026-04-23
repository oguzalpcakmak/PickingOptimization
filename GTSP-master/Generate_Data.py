# coding: utf-8
import numpy as np
import argparse

def GenerateData(points,goods,filename=None):
    goodsIdx = np.random.choice(points,goods,replace=False)
    # 首先在points个点中随机选择goods个位置，保证每一种商品都至少有一个点卖
    typeList = np.random.randint(goods,size=points)
    # 生成一个1*points的数组，typeList[i]是第i+1个点的商品种类
    for i in range(goods):
        typeList[goodsIdx[i]] = i


    goodsType = []
    for i in range(goods):
        tmpList = []
        for j in range(points):
            if typeList[j]==i:
                tmpList.append(j)
        goodsType.append(tmpList)
    # 最终goodsType是一个长度为goods的列表，goodsType[i]是第i种商品出现的几个地点坐标
    # goodsType是一个列表的列表；
    # 例如： [[0，1],[2,4],[3,5,6]]
    # 这样表示存在7个点，3种商品；第一种商品在0、1号城市有卖，第二种商品在2、4号城市卖，第三种商品在3、5、6号城市卖

    graph = np.random.randint(60,100,size=(points, points))    
    graph = np.tril(graph) + np.tril(graph, -1).T
    # 确保是一个对称矩阵
    for i in range(points):
        graph[i][i]=0
    # 每个点到自身距离为0

    if filename==None:
        np.save('TypeList_'+str(points)+'_'+str(goods)+'.npy',typeList)
        np.save('GoodsType_'+str(points)+'_'+str(goods)+'.npy',goodsType)
        np.save('Graph_'+str(points)+'.npy',graph)
    else:
        np.save(filename+'_TypeList.npy',typeList)
        np.save(filename+'_GoodsType.npy',goodsType)
        np.save(filename+'_Graph.npy',graph)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p","--pointNumber",help="地图上点的数量")
    parser.add_argument("-g","--goodNumber",help="商品的种类数量")
    parser.add_argument("-o","--file",help="数据文件名称")
    args = parser.parse_args()

    if args.goodNumber==None and args.pointNumber!=None:
        print("没有指定点的数量！")
        exit(1)
    elif args.goodNumber!=None and args.pointNumber==None:
        print("没有指定商品数量！")
        exit(1)
    elif args.goodNumber==None and args.pointNumber==None:
        defaultList = [(9,5),(17,11),(24,15),(31,16),(39,25)]

        for example in defaultList:
            GenerateData(example[0],example[1],filename=args.file)
    else:
        if args.goodNumber > args.pointNumber:
            print("商品的种类必须少于点的数量")
            exit(1)
        else:
            GenerateData(args.pointNumber,args.goodNumber,filename=args.file)

if __name__ == "__main__":
    main()